"""CrewAI-backed CV matching orchestration."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import TypeVar

from crewai import Process, Task
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.services.orchestration_progress_service import orchestration_progress_service
from crewai import Agent, Crew, LLM
from src.ai.events.runtime_context import current_run_id, current_stage
from src.ai.providers import get_model_provider
from src.ai.prompts.cv_matching import (
    CRITERIA_GRID_ANALYSIS_EXPECTED_OUTPUT,
    CRITERIA_GRID_ANALYSIS_PROMPT,
    EXP_DESIGNATION_ANALYSIS_EXPECTED_OUTPUT,
    EXP_DESIGNATION_ANALYSIS_PROMPT,
    OTHER_FACTORS_ANALYSIS_EXPECTED_OUTPUT,
    OTHER_FACTORS_ANALYSIS_PROMPT,
    OVERALL_ANALYSIS_EXPECTED_OUTPUT,
    OVERALL_ANALYSIS_PROMPT,
    SKILLS_ANALYSIS_EXPECTED_OUTPUT,
    SKILLS_ANALYSIS_PROMPT,
)
from src.ai.runtime.crewai_run_limiter import CrewAIRunLimiter
from src.shared import CrewAIRunLimits, OpenAITokenPricing, get_openai_token_pricing
from src.shared.schemas import (
    CriteriaGridOutput,
    DomainKnowledgeOutput,
    ExperienceAndDesignationAnalysis,
    MatchAnalystOutput,
    MatchSummaryOutput,
    MatchingContext,
    SkillsMatchOutput,
    OtherFactorsOutput,
)

_TOKEN_USAGE_FIELDS = (
    "total_tokens",
    "prompt_tokens",
    "cached_prompt_tokens",
    "completion_tokens",
    "reasoning_tokens",
    "cache_creation_tokens",
    "successful_requests",
)
_T = TypeVar("_T", bound=BaseModel)


def _load_task_output_model(task_output: object, model_type: type[_T]) -> _T:
    pydantic_output = getattr(task_output, "pydantic", None)
    if isinstance(pydantic_output, model_type):
        return pydantic_output

    raw_output = getattr(task_output, "raw", None)
    if isinstance(raw_output, str):
        return model_type.model_validate_json(raw_output)

    json_dict = getattr(task_output, "json_dict", None)
    if isinstance(json_dict, dict):
        return model_type.model_validate(json_dict)

    raise ValueError(f"CrewAI output could not be parsed as {model_type.__name__}.")


def _build_llm() -> LLM | None:
    provider = get_model_provider()
    if not provider.uses_live_llm:
        return None

    return LLM(
        model=f"openai/{settings.openai_model}",
        api_key=settings.openai_api_key,
        temperature=settings.default_temperature,
    )


def _build_run_pricing() -> OpenAITokenPricing | None:
    shared_pricing = get_openai_token_pricing(settings.openai_model)
    input_cost = settings.openai_input_token_cost_per_million_usd
    cached_input_cost = settings.openai_cached_input_token_cost_per_million_usd
    output_cost = settings.openai_output_token_cost_per_million_usd

    if input_cost is None and cached_input_cost is None and output_cost is None:
        return shared_pricing

    return OpenAITokenPricing(
        input_per_million_usd=(
            input_cost
            if input_cost is not None
            else (shared_pricing.input_per_million_usd if shared_pricing else 0.0)
        ),
        cached_input_per_million_usd=(
            cached_input_cost
            if cached_input_cost is not None
            else (
                shared_pricing.cached_input_per_million_usd if shared_pricing else 0.0
            )
        ),
        output_per_million_usd=(
            output_cost
            if output_cost is not None
            else (shared_pricing.output_per_million_usd if shared_pricing else 0.0)
        ),
    )


def _severity_for_label(label: str) -> str:
    if label == "match":
        return "good"
    if label in {"partial", "gap"}:
        return "warning"
    return "bad"


def _publish_step(
    run_id: str | None, event_type: str, label: str, message: str
) -> None:
    if not run_id:
        return
    try:
        orchestration_progress_service.publish_event(
            run_id,
            {
                "run_id": run_id,
                "type": event_type,
                "label": label,
                "stage": label,
                "message": message,
            },
        )
    except Exception:
        return


class CvMatchingCrew:
    def __init__(self, *, run_limits: CrewAIRunLimits | None = None) -> None:
        self.llm = _build_llm()
        self._token_usage = {field: 0 for field in _TOKEN_USAGE_FIELDS}
        self._run_limiter = CrewAIRunLimiter(
            limits=run_limits,
            pricing=_build_run_pricing(),
        )
        self._usage_lock = Lock()

    @property
    def token_usage(self) -> dict[str, int]:
        return self._token_usage.copy()

    @property
    def run_limits(self) -> CrewAIRunLimits:
        return self._run_limiter.limits

    @property
    def elapsed_seconds(self) -> float:
        return self._run_limiter.elapsed_seconds

    @property
    def estimated_cost_usd(self) -> float:
        return self._run_limiter.estimated_cost_usd(self._token_usage)

    def _bounded_execution_time(self, default_seconds: int) -> int:
        remaining_seconds = self._run_limiter.remaining_latency_seconds
        if remaining_seconds is None:
            return default_seconds
        return max(1, min(default_seconds, int(remaining_seconds)))

    def _record_token_usage(self, crew_output: object) -> None:
        usage = getattr(crew_output, "token_usage", None)
        if usage is None:
            return
        values = usage.model_dump() if hasattr(usage, "model_dump") else {}
        for field in _TOKEN_USAGE_FIELDS:
            self._token_usage[field] += int(values.get(field, 0) or 0)

    def _kickoff_with_limits(self, crew: Crew, *, operation: str) -> object:
        self._run_limiter.assert_can_start(operation=operation)
        crew_output = crew.kickoff()
        with self._usage_lock:
            self._record_token_usage(crew_output)
            self._run_limiter.assert_within_limits(
                self._token_usage, operation=operation
            )
        return crew_output

    def _fallback_analyst_output(self, context: MatchingContext) -> MatchAnalystOutput:
        facts = context.facts
        exp_gap = 0
        if facts.vacancy_min_experience_years is not None:
            exp_gap = round(
                facts.candidate_experience_years - facts.vacancy_min_experience_years, 1
            )
        if facts.vacancy_min_experience_years is None:
            exp_percent, exp_label = 65, "partial"
            exp_note = "Experience target unclear"
        elif exp_gap >= 1:
            exp_percent, exp_label = 88, "match"
            exp_note = "Experience meets requirement"
        elif exp_gap >= 0:
            exp_percent, exp_label = 75, "partial"
            exp_note = "Borderline experience fit"
        elif exp_gap >= -1:
            exp_percent, exp_label = 48, "gap"
            exp_note = "Slight experience gap"
        else:
            exp_percent, exp_label = 22, "major_gap"
            exp_note = "Experience below requirement"

        overlap_count = len(facts.title_overlap)
        if overlap_count:
            title_percent, title_label = 84, "match"
            title_note = "Relevant titles present"
        elif facts.candidate_titles:
            title_percent, title_label = 55, "partial"
            title_note = "Adjacent titles only"
        else:
            title_percent, title_label = 20, "missing"
            title_note = "Titles not available"

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
                overlap_percent
                + (
                    10 if len(context.cv_data.skills) > len(facts.matched_skills) else 0
                ),
            ),
        )

        domain_percent = min(100, max(20, round((exp_percent + skills_percent) / 2)))
        if domain_percent >= 80:
            domain_label = "match"
        elif domain_percent >= 50:
            domain_label = "partial"
        elif domain_percent >= 30:
            domain_label = "gap"
        else:
            domain_label = "major_gap"

        other_items = []
        education_level = context.vacancy_data.education_level.strip()
        if education_level:
            candidate_education = (
                context.cv_data.education_qualification or "Not specified"
            ).strip()
            education_status = (
                "match" if candidate_education != "Not specified" else "missing"
            )
            other_items.append(
                {
                    "key": "education",
                    "jd_preference": education_level,
                    "candidate_value": candidate_education,
                    "status": education_status,
                    "severity": ("good" if education_status == "match" else "missing"),
                }
            )
        if context.vacancy_data.offered_salary and (
            context.vacancy_data.offered_salary.min is not None
            or context.vacancy_data.offered_salary.max is not None
        ):
            salary_status = facts.salary_assessment.status
            other_items.append(
                {
                    "key": "salary",
                    "jd_preference": (
                        f"{facts.salary_assessment.vacancy_min or 0:g}"
                        f"-{facts.salary_assessment.vacancy_max or 0:g}"
                    ),
                    "candidate_value": (
                        "Not specified"
                        if facts.salary_assessment.candidate_min is None
                        and facts.salary_assessment.candidate_max is None
                        else (
                            f"{facts.salary_assessment.candidate_min or 0:g}"
                            f"-{facts.salary_assessment.candidate_max or 0:g}"
                        )
                    ),
                    "status": salary_status,
                    "severity": {
                        "match": "good",
                        "partial": "neutral",
                        "mismatch": "bad",
                        "missing": "missing",
                    }[salary_status],
                }
            )
        if context.vacancy_data.gender_preferred.strip():
            candidate_gender = context.cv_data.gender.strip() or "Not specified"
            if candidate_gender == "Not specified":
                gender_status = "missing"
            elif (
                candidate_gender.lower()
                == context.vacancy_data.gender_preferred.lower()
            ):
                gender_status = "match"
            else:
                gender_status = "mismatch"
            other_items.append(
                {
                    "key": "gender",
                    "jd_preference": context.vacancy_data.gender_preferred,
                    "candidate_value": candidate_gender,
                    "status": gender_status,
                    "severity": {
                        "match": "good",
                        "partial": "neutral",
                        "mismatch": "bad",
                        "missing": "missing",
                    }[gender_status],
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
                        "text": (
                            f"Candidate shows about {facts.candidate_experience_years:.1f} years of experience."
                        ),
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
                            if overlap_count
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
                        "text": (
                            f"{facts.matched_skill_count} of {facts.vacancy_skill_count} vacancy skills are explicitly evidenced."
                        ),
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
        self,
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
            fit_level = "excellent"
            recommendation = "Proceed"
        elif weighted_score >= 70:
            fit_level = "good"
            recommendation = "Proceed"
        elif weighted_score >= 55:
            fit_level = "partial"
            recommendation = "Proceed with caution"
        elif weighted_score >= 35:
            fit_level = "weak"
            recommendation = "Hold for better role fit"
        else:
            fit_level = "not_recommended"
            recommendation = "Reject for this role"

        strengths = []
        if analyst_output.experience.match.percent >= 70:
            strengths.append("Experience level is reasonably aligned.")
        if analyst_output.designation_role.match.percent >= 70:
            strengths.append("Recent titles are relevant to the vacancy.")
        if analyst_output.skills.matched_skills:
            strengths.append(
                f"Confirmed skill overlap includes {', '.join(analyst_output.skills.matched_skills[:3])}."
            )
        if not strengths:
            strengths.append("Candidate provides some evidence relevant to the role.")
        while len(strengths) < 3:
            strengths.append(
                "Work history offers at least partial role-adjacent evidence."
            )

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
            gaps.append(
                "Interview should validate depth behind the listed accomplishments."
            )

        best_fit_roles = [
            context.cv_data.designation or context.vacancy_data.title,
            context.vacancy_data.title,
        ]
        best_fit_roles = [role for role in best_fit_roles if role][:3]
        while len(best_fit_roles) < 1:
            best_fit_roles.append("Related role")

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
                "This assessment combines deterministic overlap checks with bounded LLM review. "
                "The candidate's strongest signals come from confirmed experience, title history, "
                "and explicit skill evidence, while the final recommendation is constrained by the "
                "largest gaps that still affect hiring risk."
            ),
            overall_score=weighted_score,
            overall_fit_level=fit_level,
            key_strengths=strengths[:5],
            key_gaps=gaps[:5],
            best_fit_roles=best_fit_roles[:3],
            recommended_interview_focus=interview_focus[:5],
            ai_recommendation=recommendation,
            ideal_next_step="Run a focused recruiter screen on role-critical gaps.",
            pills=[
                {"text": "Skills overlap checked", "severity": "good"},
                {"text": "Role fit bounded", "severity": "warning"},
            ],
        )

    def _task_agent(
        self,
        *,
        role: str,
        goal: str,
        backstory: str,
        max_execution_time: int,
    ) -> Agent:
        return Agent(
            role=role,
            goal=goal,
            backstory=backstory,
            llm=self.llm,
            max_iter=8,
            max_execution_time=self._bounded_execution_time(max_execution_time),
            allow_delegation=False,
            verbose=False,
        )

    def _run_structured_task(
        self,
        *,
        stage: str,
        operation: str,
        agent: Agent,
        description: str,
        expected_output: str,
        model_type: type[_T],
        run_id: str | None,
    ) -> _T:
        run_token = current_run_id.set(run_id)
        stage_token = current_stage.set(stage)
        try:
            _publish_step(run_id, "step_started", stage, f"Running {operation}.")
            task = Task(
                description=description,
                expected_output=expected_output,
                agent=agent,
                output_pydantic=model_type,
            )
            crew = Crew(
                agents=[agent],
                tasks=[task],
                process=Process.sequential,
                verbose=False,
            )
            self._kickoff_with_limits(crew, operation=operation)
            output = _load_task_output_model(task.output, model_type)
            _publish_step(run_id, "step_completed", stage, f"Completed {operation}.")
            return output
        except Exception as exc:
            _publish_step(run_id, "step_failed", stage, str(exc))
            raise
        finally:
            current_stage.reset(stage_token)
            current_run_id.reset(run_token)

    def _domain_from_branches(
        self,
        exp_des_analysis: ExperienceAndDesignationAnalysis,
        skills_analysis: SkillsMatchOutput,
    ) -> DomainKnowledgeOutput:
        percent = round(
            (exp_des_analysis.experience.match.percent + skills_analysis.match.percent)
            / 2
        )
        if percent >= 80:
            label = "match"
        elif percent >= 50:
            label = "partial"
        elif percent >= 30:
            label = "gap"
        else:
            label = "major_gap"
        return DomainKnowledgeOutput(
            match={
                "percent": percent,
                "label": label,
                "severity": _severity_for_label(label),
            },
            insight={
                "text": "Domain fit is inferred from role experience and skill evidence.",
                "confidence": min(
                    exp_des_analysis.experience.insight.confidence or 0.5,
                    skills_analysis.insight.confidence or 0.5,
                ),
            },
            status_note="Inferred from branches",
        )

    def _combine_analyst_output(
        self,
        exp_des_analysis: ExperienceAndDesignationAnalysis,
        skills_analysis: SkillsMatchOutput,
        other_factors_analysis: OtherFactorsOutput,
    ) -> MatchAnalystOutput:
        return MatchAnalystOutput(
            experience=exp_des_analysis.experience,
            designation_role=exp_des_analysis.designation_role,
            domain_knowledge=self._domain_from_branches(
                exp_des_analysis, skills_analysis
            ),
            skills=skills_analysis,
            other_factors=other_factors_analysis,
        )

    def run_match_analysis(
        self,
        context: MatchingContext,
    ) -> tuple[MatchAnalystOutput, MatchSummaryOutput, CriteriaGridOutput]:
        if self.llm is None:
            analyst_output = self._fallback_analyst_output(context)
            summary_output = self._fallback_summary_output(context, analyst_output)
            return analyst_output, summary_output, CriteriaGridOutput()

        cv_json = json.dumps(context.cv_data.model_dump(mode="json"), indent=2)
        vacancy_json = json.dumps(
            context.vacancy_data.model_dump(mode="json"), indent=2
        )
        run_id = current_run_id.get()

        with ThreadPoolExecutor(max_workers=4) as executor:
            exp_future = executor.submit(
                self._run_structured_task,
                stage="analyze_experience_designation",
                operation="experience and designation analysis",
                agent=self._task_agent(
                    role="Experience and Designation Analyst",
                    goal="Evaluate candidate experience depth and title alignment against the vacancy.",
                    backstory="You are an expert HR assistant specializing in evaluating candidate fit for job vacancies.",
                    max_execution_time=75,
                ),
                description=EXP_DESIGNATION_ANALYSIS_PROMPT.format(
                    candidate_works_json=json.dumps(
                        [
                            work.model_dump(mode="json")
                            for work in context.cv_data.works
                        ],
                        indent=2,
                    ),
                    candidate_designation=context.cv_data.designation,
                    candidate_designations_json=json.dumps(
                        context.cv_data.designations, indent=2
                    ),
                    vacancy_json=vacancy_json,
                ),
                expected_output=EXP_DESIGNATION_ANALYSIS_EXPECTED_OUTPUT,
                model_type=ExperienceAndDesignationAnalysis,
                run_id=run_id,
            )
            skills_future = executor.submit(
                self._run_structured_task,
                stage="analyze_skills",
                operation="skills match analysis",
                agent=self._task_agent(
                    role="Skills Match Analyst",
                    goal="Evaluate vacancy skill coverage using explicit candidate skill evidence.",
                    backstory="You are an expert HR assistant specializing in evaluating candidate fit for job vacancies.",
                    max_execution_time=75,
                ),
                description=SKILLS_ANALYSIS_PROMPT.format(
                    candidate_works_json=json.dumps(
                        [
                            work.model_dump(mode="json")
                            for work in context.cv_data.works
                        ],
                        indent=2,
                    ),
                    candidate_skills_json=json.dumps(context.cv_data.skills, indent=2),
                    vacancy_json=vacancy_json,
                ),
                expected_output=SKILLS_ANALYSIS_EXPECTED_OUTPUT,
                model_type=SkillsMatchOutput,
                run_id=run_id,
            )
            other_future = executor.submit(
                self._run_structured_task,
                stage="analyze_other_factors",
                operation="other factors analysis",
                agent=self._task_agent(
                    role="Other Factors Analyst",
                    goal="Evaluate explicit non-skill match factors such as education, location, salary, and gender.",
                    backstory="You are an expert HR assistant specializing in evaluating candidate fit for job vacancies.",
                    max_execution_time=60,
                ),
                description=OTHER_FACTORS_ANALYSIS_PROMPT.format(
                    candidate_education=context.cv_data.education_qualification,
                    candidate_location=context.cv_data.address,
                    candidate_salary_json=json.dumps(
                        (
                            context.cv_data.salary_expectation.model_dump(mode="json")
                            if context.cv_data.salary_expectation
                            else None
                        ),
                        indent=2,
                    ),
                    candidate_gender=context.cv_data.gender,
                    vacancy_json=vacancy_json,
                ),
                expected_output=OTHER_FACTORS_ANALYSIS_EXPECTED_OUTPUT,
                model_type=OtherFactorsOutput,
                run_id=run_id,
            )
            criteria_future = executor.submit(
                self._run_structured_task,
                stage="analyze_criteria_grid",
                operation="criteria grid analysis",
                agent=self._task_agent(
                    role="Criteria Grid Analyst",
                    goal="Create a concise criteria-by-criteria candidate-vacancy fit grid.",
                    backstory="You are an expert HR assistant specializing in evaluating candidate fit for job vacancies.",
                    max_execution_time=75,
                ),
                description=CRITERIA_GRID_ANALYSIS_PROMPT.format(
                    cv_json=cv_json,
                    vacancy_json=vacancy_json,
                ),
                expected_output=CRITERIA_GRID_ANALYSIS_EXPECTED_OUTPUT,
                model_type=CriteriaGridOutput,
                run_id=run_id,
            )

            fallback = self._fallback_analyst_output(context)
            try:
                exp_des_analysis = exp_future.result()
            except (ValidationError, ValueError):
                exp_des_analysis = ExperienceAndDesignationAnalysis(
                    experience=fallback.experience,
                    designation_role=fallback.designation_role,
                )
            try:
                skills_analysis = skills_future.result()
            except (ValidationError, ValueError):
                skills_analysis = fallback.skills
            try:
                other_factors_analysis = other_future.result()
            except (ValidationError, ValueError):
                other_factors_analysis = fallback.other_factors
            try:
                criteria_grid_analysis = criteria_future.result()
            except (ValidationError, ValueError):
                criteria_grid_analysis = CriteriaGridOutput()

        analyst_output = self._combine_analyst_output(
            exp_des_analysis, skills_analysis, other_factors_analysis
        )

        try:
            summary_output = self._run_structured_task(
                stage="analyze_overall_fit",
                operation="overall fit analysis",
                agent=self._task_agent(
                    role="Overall Fit Synthesizer",
                    goal="Synthesize completed branch analyses into final recruiter-facing guidance.",
                    backstory=(
                        "You synthesize structured fit analysis into practical hiring "
                        "guidance without overstating certainty or inventing evidence."
                    ),
                    max_execution_time=75,
                ),
                description=OVERALL_ANALYSIS_PROMPT.format(
                    cv_json=cv_json,
                    vacancy_json=vacancy_json,
                    experience_designation_json=exp_des_analysis.model_dump_json(
                        indent=2
                    ),
                    skills_json=skills_analysis.model_dump_json(indent=2),
                    other_factors_json=other_factors_analysis.model_dump_json(indent=2),
                    criteria_grid_json=criteria_grid_analysis.model_dump_json(indent=2),
                ),
                expected_output=OVERALL_ANALYSIS_EXPECTED_OUTPUT,
                model_type=MatchSummaryOutput,
                run_id=run_id,
            )
        except (ValidationError, ValueError):
            summary_output = self._fallback_summary_output(context, analyst_output)

        return analyst_output, summary_output, criteria_grid_analysis
