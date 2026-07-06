from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.services.orchestration_progress_service import orchestration_progress_service
from src.ai.events.progress_listener import ensure_progress_listener
from src.ai.events.runtime_context import current_run_id, current_stage
from src.ai.pipelines.cv_extraction_flow import run_cv_extraction_flow
from src.ai.pipelines.cv_matching_flow import run_cv_matching_flow
from src.ai.providers import get_model_provider
from src.shared.schemas import (
    CVData,
    CVMatchingRequest,
    CVMatchingResponse,
    CandidateAnalysisResponse,
    ComprehensiveCvProfile,
    CvExtractionResponse,
    DateModel,
    EducationItem,
    ExperienceLevel,
    ExecutionTraceStep,
    TraceContract,
    TraceValidation,
    VacancyData,
)
from src.shared.schemas.matching import WorkExperience as MatchingWorkExperience

_SKILL_KEYWORDS = (
    "python",
    "fastapi",
    "django",
    "flask",
    "react",
    "next.js",
    "typescript",
    "javascript",
    "node.js",
    "node",
    "redis",
    "celery",
    "docker",
    "kubernetes",
    "postgresql",
    "mysql",
    "mongodb",
    "qdrant",
    "aws",
    "gcp",
    "azure",
    "tailwind",
    "figma",
    "graphql",
    "rest",
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def _split_csv(value: str) -> list[str]:
    return _dedupe([part for part in value.replace("\n", ",").split(",")])


def _infer_skills_from_text(text: str) -> list[str]:
    lowered = text.lower()
    matched = [skill for skill in _SKILL_KEYWORDS if skill in lowered]
    return _dedupe([skill.title() if skill.islower() else skill for skill in matched])


def _infer_work_approach(text: str) -> list[str]:
    lowered = text.lower()
    approaches: list[str] = []
    if "remote" in lowered:
        approaches.append("Remote")
    if "hybrid" in lowered:
        approaches.append("Hybrid")
    if "onsite" in lowered or "on-site" in lowered:
        approaches.append("Onsite")
    return approaches


def _infer_employment_type(text: str) -> list[str]:
    lowered = text.lower()
    result: list[str] = []
    if "full time" in lowered or "full-time" in lowered:
        result.append("Full Time")
    if "part time" in lowered or "part-time" in lowered:
        result.append("Part Time")
    if "contract" in lowered:
        result.append("Contract")
    return result


def _build_vacancy_data(
    *,
    title: str,
    description: str,
    company_name: str,
    location: str,
    skills_csv: str,
) -> VacancyData:
    inferred_skills = _infer_skills_from_text(description)
    explicit_skills = _split_csv(skills_csv)
    return VacancyData(
        id=f"vacancy-{uuid4()}",
        title=title.strip() or "Untitled Role",
        description=description.strip(),
        company_name=company_name.strip(),
        location=location.strip(),
        skills_required=_dedupe([*explicit_skills, *inferred_skills]),
        employment_type=_infer_employment_type(description),
        work_approach=_infer_work_approach(description),
        experience_level=ExperienceLevel(),
    )


def _to_date_model(date_value) -> DateModel | None:
    if date_value is None:
        return None
    return DateModel(year=date_value.year, month=date_value.month)


def _profile_to_cv_data(
    *,
    candidate_id: str,
    profile: ComprehensiveCvProfile,
) -> CVData:
    personal = profile.personal_info
    professional = profile.professional_experience
    education_skills = profile.education_skills

    works = [
        MatchingWorkExperience(
            organization_name=work.organization_name,
            industry=work.industry.value,
            position=(work.designations[0] if work.designations else ""),
            still_working=work.still_working,
            start=_to_date_model(work.start),
            end=_to_date_model(work.end),
            key_responsibilities=work.key_responsibilities,
            tools=work.tools,
        )
        for work in professional.work
    ]
    education = [
        EducationItem(
            title=item.course_name,
            institution_name=item.institution_name,
            institution_address=item.institution_address,
            still_studying=item.still_studying,
            start=_to_date_model(item.start),
            end=_to_date_model(item.end),
        )
        for item in education_skills.education
    ]
    project_tools = [
        tool for project in professional.projects for tool in project.tools if tool
    ]
    work_designations = [
        designation
        for work in professional.work
        for designation in work.designations
        if designation
    ]

    return CVData(
        id=candidate_id,
        firstname=personal.firstname,
        lastname=personal.lastname,
        email=personal.email or None,
        phone=personal.phone,
        address=personal.address,
        designation=professional.primary_designation,
        designations=_dedupe([professional.primary_designation, *work_designations]),
        industry=professional.primary_industry.value,
        industries=_dedupe(
            [professional.primary_industry.value]
            + [work.industry.value for work in professional.work]
        ),
        education_qualification=education_skills.education_qualification,
        education=education,
        works=works,
        skills=_dedupe([*education_skills.skills, *project_tools]),
        about_me=personal.personal_statement,
        gender=personal.gender,
        two_wheeler=personal.two_wheeler,
        driving_license=personal.driving_license,
        note=personal.note,
    )


def _build_trace_step(
    *,
    step: str,
    agent: str,
    status: str,
    input_summary: str,
    output_summary: str,
    model_mode: str,
    started_at: str,
    ended_at: str,
    validation_ok: bool = True,
    validation_message: str = "",
) -> ExecutionTraceStep:
    return ExecutionTraceStep(
        step=step,
        agent=agent,
        status=status,
        input_contract=TraceContract(name=f"{step}.input", summary=input_summary),
        output_contract=TraceContract(name=f"{step}.output", summary=output_summary),
        validation=TraceValidation(
            ok=validation_ok,
            message=validation_message,
        ),
        started_at=started_at,
        ended_at=ended_at,
        model_mode=model_mode,
    )


def run_candidate_analysis(
    *,
    analysis_id: str | None = None,
    candidate_id: str,
    source_path: str,
    filename: str,
    content_type: str,
    job_title: str,
    job_description: str,
    company_name: str = "",
    location: str = "",
    skills_csv: str = "",
) -> CandidateAnalysisResponse:
    ensure_progress_listener()
    provider = get_model_provider()
    analysis_id = analysis_id or f"analysis-{uuid4()}"
    vacancy = _build_vacancy_data(
        title=job_title,
        description=job_description,
        company_name=company_name,
        location=location,
        skills_csv=skills_csv,
    )

    trace: list[ExecutionTraceStep] = []
    run_token = current_run_id.set(analysis_id)

    try:
        try:
            orchestration_progress_service.publish_event(
                analysis_id,
                {
                    "run_id": analysis_id,
                    "type": "run_started",
                    "label": "candidate_analysis",
                    "stage": "candidate_analysis",
                    "message": f"Started orchestration for {filename}",
                },
            )
        except Exception:
            pass
        current_stage_token = current_stage.set("cv_extraction")
        extraction_started = _utc_now()
        extraction_payload = run_cv_extraction_flow(
            candidate_id=candidate_id,
            source_path=source_path,
            filename=filename,
            content_type=content_type,
        )
        extraction_ended = _utc_now()
        current_stage.reset(current_stage_token)
        extraction = CvExtractionResponse.model_validate(extraction_payload)
        trace.append(
            _build_trace_step(
                step="cv_extraction",
                agent="Resume Extraction Specialist",
                status="completed",
                input_summary=f"Uploaded file {filename} parsed and validated before structuring.",
                output_summary=(
                    "Structured candidate profile generated."
                    if extraction.structured_profile
                    else "No structured profile returned."
                ),
                model_mode=provider.mode,
                started_at=extraction_started,
                ended_at=extraction_ended,
                validation_ok=extraction.validation.is_resume,
                validation_message=extraction.validation.reason,
            )
        )

        if extraction.structured_profile is None or not extraction.validation.is_resume:
            trace.append(
                _build_trace_step(
                    step="cv_matching",
                    agent="Match Analyst",
                    status="skipped",
                    input_summary="Matching requires a validated resume and structured profile.",
                    output_summary="Matching skipped because extraction did not yield a valid resume profile.",
                    model_mode=provider.mode,
                    started_at=extraction_ended,
                    ended_at=_utc_now(),
                    validation_ok=False,
                    validation_message="Upstream validation failed.",
                )
            )
            return CandidateAnalysisResponse(
                analysis_id=analysis_id,
                candidate_id=candidate_id,
                model_provider=provider.name,
                model_mode=provider.mode,
                provider_reason=provider.reason,
                extraction=extraction,
                vacancy=vacancy,
                matching=None,
                trace=trace,
            )

        matching_started = _utc_now()
        current_stage_token = current_stage.set("cv_matching")
        matching_request = CVMatchingRequest(
            cv_data=_profile_to_cv_data(
                candidate_id=candidate_id,
                profile=extraction.structured_profile,
            ),
            vacancy_data=vacancy,
        )
        matching_payload = run_cv_matching_flow(matching_request)
        matching_ended = _utc_now()
        current_stage.reset(current_stage_token)
        matching = CVMatchingResponse.model_validate(matching_payload)
        trace.append(
            _build_trace_step(
                step="cv_matching",
                agent="Match Analyst",
                status="completed",
                input_summary="Structured candidate profile and vacancy contract were compared.",
                output_summary="Match score, strengths, gaps, and interview guidance produced.",
                model_mode=provider.mode,
                started_at=matching_started,
                ended_at=matching_ended,
            )
        )

        return CandidateAnalysisResponse(
            analysis_id=analysis_id,
            candidate_id=candidate_id,
            model_provider=provider.name,
            model_mode=provider.mode,
            provider_reason=provider.reason,
            extraction=extraction,
            vacancy=vacancy,
            matching=matching,
            trace=trace,
        )
    finally:
        current_run_id.reset(run_token)
