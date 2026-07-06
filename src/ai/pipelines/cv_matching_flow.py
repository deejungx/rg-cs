"""Practical CV matching pipeline."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.core.config import settings
from src.ai.providers import get_model_provider
from src.ai.tracing.run_logger import append_log
from src.shared import CrewAIRunLimits
from src.shared.schemas import (
    CVMatchingRequest,
    CVMatchingResponse,
    CandidateProfile,
    CandidateSnapshot,
    CompanyLine,
    CriteriaGrid,
    CriteriaRow,
    DesignationRoleSection,
    ExperienceJobRequirement,
    ExperienceSection,
    Header,
    Insight,
    JDMatchOverview,
    LocationAssessment,
    MatchAnalystOutput,
    MatchBadge,
    MatchMeta,
    MatchSummaryOutput,
    MatchingContext,
    MatchingFacts,
    OtherFactorItem,
    OtherFactorsSection,
    OverallAIAnalysis,
    Pill,
    SalaryAssessment,
    SalaryRangeResponse,
    Scorecard,
    Sections,
    SkillsCoverage,
    SkillsSection,
)

_LOCATION_CLUSTERS = {
    "kathmandu": {"kathmandu", "katmandu", "ktm", "lalitpur", "patan", "bhaktapur"},
    "pokhara": {"pokhara", "lakeside", "chipledhunga"},
}
_SKILL_ALIASES = {
    "react.js": "react",
    "reactjs": "react",
    "node.js": "nodejs",
    "node js": "nodejs",
    "javascript": "js",
    "js": "js",
    "typescript": "ts",
    "figma design": "figma",
    "ui/ux": "ui ux",
    "ui ux": "ui ux",
    "ux/ui": "ui ux",
}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _normalize_token(value: str) -> str:
    normalized = "".join(ch.lower() if ch.isalnum() else " " for ch in value).split()
    token = " ".join(normalized)
    return _SKILL_ALIASES.get(token, token)


def _normalize_location(value: str) -> str:
    token = _normalize_token(value)
    for primary, cluster in _LOCATION_CLUSTERS.items():
        if token in cluster:
            return primary.title()
    return token.title()


def _months_from_date(date_value) -> int | None:
    if date_value is None:
        return None
    month = date_value.month or 1
    return (date_value.year * 12) + month


def _experience_months(cv_data) -> int:
    total = 0
    current = _months_from_date(
        type("Now", (), {"year": datetime.now(UTC).year, "month": datetime.now(UTC).month})()
    )
    for work in cv_data.works:
        start = _months_from_date(work.start)
        if start is None:
            continue
        end = _months_from_date(work.end)
        if end is None and work.still_working:
            end = current
        if end is None or end < start:
            continue
        total += end - start
    return total


def _extract_experience_bounds(vacancy_data) -> tuple[int | None, int | None]:
    if vacancy_data.experience_level:
        return vacancy_data.experience_level.min, vacancy_data.experience_level.max

    raw = str(vacancy_data.experience_required or "").lower()
    digits = [int(token) for token in raw.replace("+", " ").replace("-", " ").split() if token.isdigit()]
    if not digits:
        return None, None
    if len(digits) == 1:
        return digits[0], None
    return min(digits), max(digits)


def _skill_overlap(cv_data, vacancy_data) -> tuple[list[str], list[str]]:
    candidate_tokens = {_normalize_token(skill): skill for skill in cv_data.skills if skill}
    work_tokens = {
        _normalize_token(tool): tool
        for work in cv_data.works
        for tool in ([work.position] + work.tools + work.key_responsibilities)
        if tool
    }
    matched: list[str] = []
    missing: list[str] = []
    for skill in vacancy_data.skills_required:
        normalized = _normalize_token(skill)
        if normalized in candidate_tokens or normalized in work_tokens:
            matched.append(skill)
        else:
            missing.append(skill)
    return matched, missing


def _title_overlap(cv_data, vacancy_data) -> tuple[list[str], list[str], list[str]]:
    candidate_titles = [
        title for title in [cv_data.designation, *cv_data.designations] if title
    ]
    vacancy_titles = [vacancy_data.title] if vacancy_data.title else []
    vacancy_tokens = {_normalize_token(title) for title in vacancy_titles}
    overlap = [
        title
        for title in candidate_titles
        if _normalize_token(title) in vacancy_tokens
    ]
    return candidate_titles, vacancy_titles, overlap


def _location_assessment(cv_data, vacancy_data) -> LocationAssessment:
    candidate_location = cv_data.address or ""
    vacancy_location = vacancy_data.location or ""
    normalized_candidate = _normalize_location(candidate_location) if candidate_location else ""
    normalized_vacancy = _normalize_location(vacancy_location) if vacancy_location else ""
    exact_match = bool(normalized_candidate and normalized_candidate == normalized_vacancy)
    nearby_match = exact_match
    if normalized_candidate and normalized_vacancy:
        nearby_match = exact_match or (
            normalized_candidate in {city.title() for city in _LOCATION_CLUSTERS.get(normalized_vacancy.lower(), set())}
        )

    work_approach = vacancy_data.work_approach or []
    candidate_has_transport = bool(cv_data.driving_license or cv_data.two_wheeler)
    if not vacancy_location:
        status = "missing"
        note = "Location not specified"
    elif any("remote" in approach.lower() for approach in work_approach):
        status = "match" if candidate_location else "partial"
        note = "Remote role reduces location risk"
    elif nearby_match and candidate_has_transport:
        status = "match"
        note = "Commutable location fit"
    elif nearby_match:
        status = "partial"
        note = "Nearby but transport unclear"
    elif candidate_location:
        status = "mismatch"
        note = "Different work location"
    else:
        status = "missing"
        note = "Candidate location missing"

    return LocationAssessment(
        candidate_location=candidate_location,
        vacancy_location=vacancy_location,
        normalized_candidate_location=normalized_candidate,
        normalized_vacancy_location=normalized_vacancy,
        work_approach=work_approach,
        nearby_match=nearby_match,
        exact_match=exact_match,
        candidate_has_transport=candidate_has_transport,
        status=status,
        status_note=note,
    )


def _salary_assessment(cv_data, vacancy_data) -> SalaryAssessment:
    candidate = cv_data.salary_expectation
    vacancy = vacancy_data.offered_salary
    if vacancy is None or (vacancy.min is None and vacancy.max is None):
        return SalaryAssessment(status="missing", status_note="Salary not specified")
    if candidate is None or (candidate.min is None and candidate.max is None):
        return SalaryAssessment(
            vacancy_min=vacancy.min,
            vacancy_max=vacancy.max,
            status="missing",
            status_note="Candidate expectation missing",
        )

    candidate_floor = candidate.min if candidate.min is not None else candidate.max
    candidate_ceiling = candidate.max if candidate.max is not None else candidate.min
    vacancy_floor = vacancy.min if vacancy.min is not None else vacancy.max
    vacancy_ceiling = vacancy.max if vacancy.max is not None else vacancy.min

    if candidate_floor is None or candidate_ceiling is None or vacancy_floor is None or vacancy_ceiling is None:
        status = "partial"
        note = "Salary data incomplete"
    elif candidate_floor <= vacancy_ceiling and candidate_ceiling >= vacancy_floor:
        status = "match"
        note = "Salary ranges overlap"
    elif candidate_floor <= vacancy_ceiling * 1.1:
        status = "partial"
        note = "Expectation slightly above budget"
    else:
        status = "mismatch"
        note = "Expectation exceeds budget"

    return SalaryAssessment(
        candidate_min=candidate.min,
        candidate_max=candidate.max,
        vacancy_min=vacancy.min,
        vacancy_max=vacancy.max,
        status=status,
        status_note=note,
    )


def _build_context(request: CVMatchingRequest) -> MatchingContext:
    candidate_experience_months = _experience_months(request.cv_data)
    min_years, max_years = _extract_experience_bounds(request.vacancy_data)
    matched_skills, missing_skills = _skill_overlap(request.cv_data, request.vacancy_data)
    candidate_titles, vacancy_titles, title_overlap = _title_overlap(
        request.cv_data, request.vacancy_data
    )

    facts = MatchingFacts(
        candidate_experience_months=candidate_experience_months,
        candidate_experience_years=round(candidate_experience_months / 12, 1),
        vacancy_min_experience_years=min_years,
        vacancy_max_experience_years=max_years,
        matched_skill_count=len(matched_skills),
        vacancy_skill_count=len(request.vacancy_data.skills_required),
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        candidate_titles=candidate_titles,
        vacancy_titles=vacancy_titles,
        title_overlap=title_overlap,
        candidate_industries=[
            value for value in [request.cv_data.industry, *request.cv_data.industries] if value
        ],
        vacancy_industry=request.vacancy_data.company_industry or request.vacancy_data.category,
        location_assessment=_location_assessment(request.cv_data, request.vacancy_data),
        salary_assessment=_salary_assessment(request.cv_data, request.vacancy_data),
    )

    evidence = {
        "candidate_summary": {
            "full_name": request.cv_data.full_name,
            "designation": request.cv_data.designation,
            "skills": request.cv_data.skills[:25],
            "education_qualification": request.cv_data.education_qualification,
        },
        "vacancy_summary": {
            "title": request.vacancy_data.title,
            "skills_required": request.vacancy_data.skills_required[:25],
            "work_approach": request.vacancy_data.work_approach,
            "location": request.vacancy_data.location,
        },
    }

    return MatchingContext(
        cv_data=request.cv_data,
        vacancy_data=request.vacancy_data,
        facts=facts,
        evidence=evidence,
    )


def _score_to_label(score: int | None) -> str:
    if score is None:
        return "missing"
    if score >= 80:
        return "match"
    if score >= 50:
        return "partial"
    if score >= 30:
        return "gap"
    return "major_gap"


def _severity_for_label(label: str) -> str:
    if label == "match":
        return "good"
    if label in {"partial", "gap"}:
        return "warning"
    return "bad"


def _fallback_analyst_output(context: MatchingContext) -> MatchAnalystOutput:
    facts = context.facts
    exp_gap = 0
    if facts.vacancy_min_experience_years is not None:
        exp_gap = round(
            facts.candidate_experience_years - facts.vacancy_min_experience_years, 1
        )
    if facts.vacancy_min_experience_years is None:
        exp_percent, exp_label, exp_note = 65, "partial", "Experience target unclear"
    elif exp_gap >= 1:
        exp_percent, exp_label, exp_note = 88, "match", "Experience meets requirement"
    elif exp_gap >= 0:
        exp_percent, exp_label, exp_note = 75, "partial", "Borderline experience fit"
    elif exp_gap >= -1:
        exp_percent, exp_label, exp_note = 48, "gap", "Slight experience gap"
    else:
        exp_percent, exp_label, exp_note = 22, "major_gap", "Experience below requirement"

    if facts.title_overlap:
        title_percent, title_label, title_note = 84, "match", "Relevant titles present"
    elif facts.candidate_titles:
        title_percent, title_label, title_note = 55, "partial", "Adjacent titles only"
    else:
        title_percent, title_label, title_note = 20, "missing", "Titles not available"

    overlap_percent = (
        round((facts.matched_skill_count / max(1, facts.vacancy_skill_count)) * 100)
        if facts.vacancy_skill_count
        else 0
    )
    if overlap_percent >= 75:
        skills_label = "match"
    elif overlap_percent >= 50:
        skills_label = "partial"
    elif overlap_percent >= 25:
        skills_label = "gap"
    elif facts.vacancy_skill_count:
        skills_label = "major_gap"
    else:
        skills_label = "missing"

    skills_percent = min(
        100,
        max(
            0,
            overlap_percent + (10 if len(context.cv_data.skills) > len(facts.matched_skills) else 0),
        ),
    )
    domain_percent = min(100, max(20, round((exp_percent + skills_percent) / 2)))
    domain_label = _score_to_label(domain_percent)

    other_items = []
    if context.vacancy_data.education_level:
        candidate_education = context.cv_data.education_qualification or "Not specified"
        education_status = "match" if candidate_education != "Not specified" else "missing"
        other_items.append(
            {
                "key": "education",
                "jd_preference": context.vacancy_data.education_level,
                "candidate_value": candidate_education,
                "status": education_status,
                "severity": "good" if education_status == "match" else "missing",
            }
        )
    if facts.location_assessment.vacancy_location:
        other_items.append(
            {
                "key": "location",
                "jd_preference": facts.location_assessment.vacancy_location,
                "candidate_value": facts.location_assessment.candidate_location or "Not specified",
                "status": facts.location_assessment.status,
                "severity": {
                    "match": "good",
                    "partial": "neutral",
                    "mismatch": "bad",
                    "missing": "missing",
                }[facts.location_assessment.status],
            }
        )
    if context.vacancy_data.offered_salary:
        other_items.append(
            {
                "key": "salary",
                "jd_preference": (
                    f"{facts.salary_assessment.vacancy_min or 0:g}-{facts.salary_assessment.vacancy_max or 0:g}"
                ),
                "candidate_value": (
                    "Not specified"
                    if facts.salary_assessment.candidate_min is None
                    and facts.salary_assessment.candidate_max is None
                    else (
                        f"{facts.salary_assessment.candidate_min or 0:g}-"
                        f"{facts.salary_assessment.candidate_max or 0:g}"
                    )
                ),
                "status": facts.salary_assessment.status,
                "severity": {
                    "match": "good",
                    "partial": "neutral",
                    "mismatch": "bad",
                    "missing": "missing",
                }[facts.salary_assessment.status],
            }
        )

    return MatchAnalystOutput.model_validate(
        {
            "experience": {
                "match": {
                    "percent": exp_percent,
                    "label": exp_label,
                    "severity": _severity_for_label(exp_label),
                },
                "insight": {
                    "text": f"Candidate shows about {facts.candidate_experience_years:.1f} years of experience.",
                    "confidence": 0.65,
                },
                "status_note": exp_note,
            },
            "designation_role": {
                "match": {
                    "percent": title_percent,
                    "label": title_label,
                    "severity": _severity_for_label(title_label),
                },
                "insight": {
                    "text": (
                        "Recent titles align with the vacancy."
                        if facts.title_overlap
                        else "Title evidence is adjacent rather than exact."
                    ),
                    "confidence": 0.6,
                },
                "status_note": title_note,
            },
            "domain_knowledge": {
                "match": {
                    "percent": domain_percent,
                    "label": domain_label,
                    "severity": _severity_for_label(domain_label),
                },
                "insight": {
                    "text": "Domain fit estimated from work history, titles, and skills.",
                    "confidence": 0.5,
                },
                "status_note": "Domain fit estimated",
            },
            "skills": {
                "match": {
                    "percent": skills_percent,
                    "label": skills_label,
                    "severity": _severity_for_label(skills_label),
                },
                "matched_skills": facts.matched_skills,
                "missing_or_weak_skills": facts.missing_skills,
                "bonus_skills": [],
                "insight": {
                    "text": f"{facts.matched_skill_count} of {facts.vacancy_skill_count} vacancy skills are explicitly evidenced.",
                    "confidence": 0.7,
                },
                "coverage": {
                    "overlap_percent": overlap_percent,
                    "notes": "Based on direct overlap between vacancy skills and candidate evidence.",
                },
                "status": skills_label,
                "status_note": "Skill overlap estimated",
            },
            "other_factors": {"items": other_items},
        }
    )


def _fallback_summary_output(
    context: MatchingContext,
    analyst_output: MatchAnalystOutput,
) -> MatchSummaryOutput:
    weighted_score = round(
        (
            analyst_output.experience.match.percent * 0.3
            + analyst_output.designation_role.match.percent * 0.2
            + analyst_output.domain_knowledge.match.percent * 0.15
            + analyst_output.skills.match.percent * 0.35
        )
    )
    if weighted_score >= 85:
        fit_level, recommendation = "excellent", "Proceed"
    elif weighted_score >= 70:
        fit_level, recommendation = "good", "Proceed"
    elif weighted_score >= 55:
        fit_level, recommendation = "partial", "Proceed with caution"
    elif weighted_score >= 35:
        fit_level, recommendation = "weak", "Hold for better role fit"
    else:
        fit_level, recommendation = "not_recommended", "Reject for this role"

    strengths = []
    if analyst_output.experience.match.percent >= 70:
        strengths.append("Experience level is reasonably aligned.")
    if analyst_output.designation_role.match.percent >= 70:
        strengths.append("Recent titles are relevant to the vacancy.")
    if analyst_output.skills.matched_skills:
        strengths.append(
            f"Confirmed skill overlap includes {', '.join(analyst_output.skills.matched_skills[:3])}."
        )
    while len(strengths) < 3:
        strengths.append("Work history offers at least partial role-adjacent evidence.")

    gaps = []
    if analyst_output.skills.missing_or_weak_skills:
        gaps.append(
            f"Key missing skills include {', '.join(analyst_output.skills.missing_or_weak_skills[:3])}."
        )
    if analyst_output.experience.match.percent < 60:
        gaps.append("Experience depth may be below the role target.")
    if analyst_output.designation_role.match.percent < 60:
        gaps.append("Title alignment is not yet strong enough for a clean match.")
    if not gaps:
        gaps.append("Interview should validate depth behind the listed accomplishments.")

    best_fit_roles = [
        role
        for role in [context.cv_data.designation, context.vacancy_data.title]
        if role
    ][:3]

    interview_focus = [
        "Depth of hands-on ownership in recent roles",
        "Evidence behind the strongest listed skills",
    ]
    if analyst_output.skills.missing_or_weak_skills:
        interview_focus.append(
            f"Capability gap around {analyst_output.skills.missing_or_weak_skills[0]}"
        )

    return MatchSummaryOutput(
        headline=f"{fit_level.replace('_', ' ').title()} fit for {context.vacancy_data.title}",
        overall_summary=(
            "This assessment combines deterministic overlap checks with bounded analysis. "
            "The strongest signals come from explicit experience, title history, and skill evidence, "
            "while the recommendation is constrained by the largest remaining hiring risks."
        ),
        overall_score=weighted_score,
        overall_fit_level=fit_level,
        key_strengths=strengths[:5],
        key_gaps=gaps[:5],
        best_fit_roles=best_fit_roles or [context.vacancy_data.title],
        recommended_interview_focus=interview_focus[:5],
        ai_recommendation=recommendation,
        ideal_next_step="Run a focused recruiter screen on role-critical gaps.",
        pills=[
            {"text": "Skills overlap checked", "severity": "good"},
            {"text": "Role fit bounded", "severity": "warning"},
        ],
    )


def _criteria_rows(context: MatchingContext, analyst: MatchAnalystOutput) -> list[CriteriaRow]:
    education_status = "missing"
    education_note = "Education not specified"
    if context.vacancy_data.education_level:
        if context.cv_data.education_qualification:
            education_status = "match"
            education_note = "Qualification listed"
        else:
            education_note = "Qualification missing"

    salary_status = context.facts.salary_assessment.status
    salary_label = {
        "match": "match",
        "partial": "partial",
        "mismatch": "mismatch",
        "missing": "missing",
    }[salary_status]
    location_status = context.facts.location_assessment.status
    location_label = {
        "match": "match",
        "partial": "partial",
        "mismatch": "mismatch",
        "missing": "missing",
    }[location_status]

    return [
        CriteriaRow(
            criterion="Core Skills",
            jd_requirement=", ".join(context.vacancy_data.skills_required[:4]) or None,
            cv_summary=", ".join(analyst.skills.matched_skills[:4]) or None,
            label=analyst.skills.match.label,
            status_note=analyst.skills.status_note,
            score=analyst.skills.match.percent,
        ),
        CriteriaRow(
            criterion="Experience Level",
            jd_requirement=(
                context.vacancy_data.experience_level.level
                or (
                    f"{context.facts.vacancy_min_experience_years}+ years"
                    if context.facts.vacancy_min_experience_years is not None
                    else None
                )
            ),
            cv_summary=f"{context.facts.candidate_experience_years:.1f} years experience",
            label=analyst.experience.match.label,
            status_note=analyst.experience.status_note,
            score=analyst.experience.match.percent,
        ),
        CriteriaRow(
            criterion="Domain Knowledge",
            jd_requirement=context.facts.vacancy_industry or context.vacancy_data.category or None,
            cv_summary=", ".join(context.facts.candidate_industries[:2]) or context.cv_data.designation or None,
            label=analyst.domain_knowledge.match.label,
            status_note=analyst.domain_knowledge.status_note,
            score=analyst.domain_knowledge.match.percent,
        ),
        CriteriaRow(
            criterion="Education",
            label=education_status,
            status_note=education_note,
            score=100 if education_status == "match" else None,
        ),
        CriteriaRow(
            criterion="Industry Alignment",
            jd_requirement=context.facts.vacancy_industry or None,
            cv_summary=", ".join(context.facts.candidate_industries[:2]) or None,
            label=(
                "match"
                if context.facts.vacancy_industry
                and any(
                    _normalize_token(industry) == _normalize_token(context.facts.vacancy_industry)
                    for industry in context.facts.candidate_industries
                )
                else "partial"
                if context.facts.candidate_industries
                else "missing"
            ),
            status_note=(
                "Industry overlap found"
                if context.facts.vacancy_industry
                and any(
                    _normalize_token(industry) == _normalize_token(context.facts.vacancy_industry)
                    for industry in context.facts.candidate_industries
                )
                else "Industry fit unclear"
            ),
            score=(
                85
                if context.facts.vacancy_industry
                and any(
                    _normalize_token(industry) == _normalize_token(context.facts.vacancy_industry)
                    for industry in context.facts.candidate_industries
                )
                else 55
                if context.facts.candidate_industries
                else None
            ),
        ),
        CriteriaRow(
            criterion="Job Title Similarity",
            label=analyst.designation_role.match.label,
            status_note=analyst.designation_role.status_note,
            score=analyst.designation_role.match.percent,
        ),
        CriteriaRow(
            criterion="Skills Overlap",
            jd_requirement=f"{context.facts.vacancy_skill_count} required skills" if context.facts.vacancy_skill_count else None,
            cv_summary=f"{context.facts.matched_skill_count} explicitly matched" if context.facts.vacancy_skill_count else None,
            label=analyst.skills.match.label,
            status_note=analyst.skills.coverage.notes,
            score=analyst.skills.coverage.overlap_percent,
        ),
        CriteriaRow(
            criterion="Location",
            jd_requirement=context.vacancy_data.location or None,
            cv_summary=context.cv_data.address or None,
            label=location_label,
            status_note=context.facts.location_assessment.status_note,
            score=None,
        ),
        CriteriaRow(
            criterion="Salary Expectation",
            label=salary_label,
            status_note=context.facts.salary_assessment.status_note,
            score=None,
        ),
    ]


def _assemble_response(
    context: MatchingContext,
    analyst: MatchAnalystOutput,
    summary: MatchSummaryOutput,
) -> CVMatchingResponse:
    criteria_rows = _criteria_rows(context, analyst)

    return CVMatchingResponse(
        meta=MatchMeta(
            analysis_id=str(uuid4()),
            created_at=_utc_now(),
            candidate_id=context.cv_data.id,
            vacancy_id=context.vacancy_data.id,
        ),
        candidate_snapshot=CandidateSnapshot(
            full_name=context.cv_data.full_name or "Unknown",
            work_status=context.cv_data.current_status,
            phone=context.cv_data.phone,
            email=context.cv_data.email,
            designation=context.cv_data.designation,
            salary_expectation=(
                SalaryRangeResponse.model_validate(
                    context.cv_data.salary_expectation.model_dump(mode="json")
                )
                if context.cv_data.salary_expectation
                else None
            ),
        ),
        jd_match_overview=JDMatchOverview(
            header=Header(
                jd_title=context.vacancy_data.title,
                company_line=CompanyLine(
                    company_name=context.vacancy_data.company_name,
                    location=context.vacancy_data.location,
                    employment_type_display=", ".join(context.vacancy_data.employment_type),
                    work_approach_display=", ".join(context.vacancy_data.work_approach),
                ),
                overall_match=MatchBadge(
                    percent=summary.overall_score,
                    label=(
                        "match"
                        if summary.overall_fit_level in {"excellent", "good"}
                        else "partial"
                        if summary.overall_fit_level == "partial"
                        else "mismatch"
                    ),
                    severity=(
                        "good"
                        if summary.overall_fit_level in {"excellent", "good"}
                        else "warning"
                        if summary.overall_fit_level == "partial"
                        else "bad"
                    ),
                ),
                pills=[Pill(text=item.text, severity=item.severity) for item in summary.pills],
            ),
            scorecards=[
                Scorecard(
                    key="experience",
                    title="Experience Match",
                    match=MatchBadge.model_validate(analyst.experience.match.model_dump()),
                ),
                Scorecard(
                    key="designation_role",
                    title="Designation Match",
                    match=MatchBadge.model_validate(analyst.designation_role.match.model_dump()),
                ),
                Scorecard(
                    key="skills",
                    title="Skills Match",
                    match=MatchBadge.model_validate(analyst.skills.match.model_dump()),
                ),
            ],
            sections=Sections(
                experience=ExperienceSection(
                    match=MatchBadge.model_validate(analyst.experience.match.model_dump()),
                    job_requirement=ExperienceJobRequirement(
                        headline="Experience Requirement",
                        experience_level=(
                            context.vacancy_data.experience_level.level
                            or (
                                f"{context.facts.vacancy_min_experience_years}+ years"
                                if context.facts.vacancy_min_experience_years is not None
                                else ""
                            )
                        ),
                    ),
                    candidate_profile=CandidateProfile(
                        headline=analyst.experience.status_note,
                        detail=analyst.experience.insight.text,
                    ),
                    insight=Insight.model_validate(analyst.experience.insight.model_dump()),
                ),
                designation_role=DesignationRoleSection(
                    match=MatchBadge.model_validate(analyst.designation_role.match.model_dump()),
                    job_title_options=context.facts.vacancy_titles,
                    candidate_titles=context.facts.candidate_titles,
                    insight=Insight.model_validate(
                        analyst.designation_role.insight.model_dump()
                    ),
                ),
                skills=SkillsSection(
                    match=MatchBadge.model_validate(analyst.skills.match.model_dump()),
                    matched_skills=analyst.skills.matched_skills,
                    missing_or_weak_skills=analyst.skills.missing_or_weak_skills,
                    bonus_skills=analyst.skills.bonus_skills,
                    insight=Insight.model_validate(analyst.skills.insight.model_dump()),
                    coverage=SkillsCoverage.model_validate(
                        analyst.skills.coverage.model_dump()
                    ),
                ),
                other_factors=OtherFactorsSection(
                    items=[
                        OtherFactorItem(
                            key=item.key,
                            jd_preference=item.jd_preference,
                            candidate_value=item.candidate_value,
                            label=item.status,
                            severity=item.severity,
                        )
                        for item in analyst.other_factors.items
                    ]
                )
                if analyst.other_factors.items
                else None,
                overall_ai_analysis=OverallAIAnalysis(
                    headline=summary.headline,
                    overall_summary=summary.overall_summary,
                    overall_fit_level=summary.overall_fit_level,
                    key_strengths=summary.key_strengths,
                    key_gaps=summary.key_gaps,
                    best_fit_roles=summary.best_fit_roles,
                    recommended_interview_focus=summary.recommended_interview_focus,
                    ai_recommendation=summary.ai_recommendation,
                    ideal_next_step=summary.ideal_next_step,
                ),
            ),
            criteria_grid=CriteriaGrid(rows=criteria_rows),
        ),
    )


def run_cv_matching_flow(
    request: CVMatchingRequest,
    *,
    max_cost_usd: float | None = None,
    max_latency_seconds: float | None = None,
) -> dict[str, object]:
    run_limits = CrewAIRunLimits(
        max_cost_usd=(
            settings.crewai_run_max_cost_usd
            if max_cost_usd is None
            else max_cost_usd
        ),
        max_latency_seconds=(
            settings.crewai_run_max_latency_seconds
            if max_latency_seconds is None
            else max_latency_seconds
        ),
    )
    context = _build_context(request)
    token_usage: dict[str, int] = {}
    estimated_cost_usd = 0.0
    elapsed_seconds = 0.0
    provider = get_model_provider()
    if provider.uses_live_llm:
        from src.ai.crews.cv_matching_crew import CvMatchingCrew

        crew = CvMatchingCrew(run_limits=run_limits)
        analyst_output, summary_output = crew.run_match_analysis(context)
        token_usage = crew.token_usage
        estimated_cost_usd = crew.estimated_cost_usd
        elapsed_seconds = crew.elapsed_seconds
    else:
        analyst_output = _fallback_analyst_output(context)
        summary_output = _fallback_summary_output(context, analyst_output)

    response = _assemble_response(context, analyst_output, summary_output)
    append_log(
        run_id=context.cv_data.id,
        event={
            "stage": "cv_matching",
            "candidate_id": context.cv_data.id,
            "vacancy_id": context.vacancy_data.id,
            "token_usage": token_usage,
            "estimated_cost_usd": estimated_cost_usd,
            "elapsed_seconds": elapsed_seconds,
        },
    )
    return response.model_dump(mode="json")
