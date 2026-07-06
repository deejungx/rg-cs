import json
from collections.abc import Mapping, Sequence
from typing import Any, TypeVar

from crewai import Process, Task
from app.core.config import settings
from pydantic import BaseModel, ValidationError
from src.ai.formatters.cv_markdown import render_cv_markdown
from src.ai.integrations.deepeval_crewai import Agent, Crew, LLM, initialize_deepeval
from src.ai.providers import get_model_provider
from src.ai.prompts.cv_extraction import CV_MARKDOWN_PROMPT
from src.ai.runtime.crewai_run_limiter import CrewAIRunLimiter
from src.ai.tracing.phoenix import initialize_phoenix
from src.shared import CrewAIRunLimits, OpenAITokenPricing, get_openai_token_pricing
from src.shared.schemas import ComprehensiveCvProfile, ResumeValidationResult

_TOKEN_USAGE_FIELDS = (
    "total_tokens",
    "prompt_tokens",
    "cached_prompt_tokens",
    "completion_tokens",
    "reasoning_tokens",
    "cache_creation_tokens",
    "successful_requests",
)

_PLACEHOLDER_VALUES = {
    "n/a",
    "na",
    "none",
    "null",
    "unknown",
    "not provided",
    "not specified",
}
_REQUIRED_MARKDOWN_HEADINGS = (
    "## At a Glance",
    "## Contact",
    "## Profile",
    "## Skills",
    "## Work Experience",
    "## Projects",
    "## Education",
    "## Training and Certifications",
    "## Extraction Notes",
)
_T = TypeVar("_T", bound=BaseModel)


def _load_task_output_model(task_output: object, model_type: type[_T]) -> _T:
    pydantic_output = getattr(task_output, "pydantic", None)
    if isinstance(pydantic_output, model_type):
        return pydantic_output

    raw_output = getattr(task_output, "raw", None)
    if isinstance(raw_output, str):
        try:
            return model_type.model_validate_json(raw_output)
        except ValidationError:
            pass
        except json.JSONDecodeError:
            pass

    json_dict = getattr(task_output, "json_dict", None)
    if isinstance(json_dict, dict):
        return model_type.model_validate(json_dict)

    raise ValueError(f"CrewAI output could not be parsed as {model_type.__name__}.")


def _collect_placeholder_paths(value: Any, path: str = "root") -> list[str]:
    if isinstance(value, str):
        normalized = value.strip().lower()
        return [path] if normalized in _PLACEHOLDER_VALUES else []
    if isinstance(value, Mapping):
        paths: list[str] = []
        for key, child in value.items():
            paths.extend(_collect_placeholder_paths(child, f"{path}.{key}"))
        return paths
    if isinstance(value, Sequence) and not isinstance(value, str):
        paths: list[str] = []
        for index, child in enumerate(value):
            paths.extend(_collect_placeholder_paths(child, f"{path}[{index}]"))
        return paths
    return []


def _validate_profile_quality(profile: ComprehensiveCvProfile) -> list[str]:
    issues: list[str] = []
    personal = profile.personal_info
    professional = profile.professional_experience
    education_skills = profile.education_skills

    evidence_signals = [
        bool(personal.firstname or personal.lastname),
        bool(personal.email or personal.phone or personal.address),
        bool(professional.primary_designation),
        bool(professional.work),
        bool(professional.projects),
        bool(education_skills.education),
        bool(education_skills.skills),
        bool(education_skills.training),
    ]
    if not any(evidence_signals):
        issues.append(
            "The profile is schema-valid but effectively empty. Extract supported candidate details before returning."
        )

    placeholder_paths = _collect_placeholder_paths(profile.model_dump(mode="json"))
    if placeholder_paths:
        issues.append(
            "Replace placeholder strings such as N/A or Unknown with schema defaults. "
            f"Affected fields: {', '.join(placeholder_paths[:6])}."
        )

    for work_index, work in enumerate(professional.work, start=1):
        if work.still_working is True and work.end is not None:
            issues.append(
                f"Work entry {work_index} marks the role as current but also includes an end date."
            )
        if work.start and work.end:
            start_tuple = (work.start.year, work.start.month or 0)
            end_tuple = (work.end.year, work.end.month or 0)
            if start_tuple > end_tuple:
                issues.append(
                    f"Work entry {work_index} has a start date later than its end date."
                )

    for education_index, education in enumerate(education_skills.education, start=1):
        if education.start and education.end:
            start_tuple = (education.start.year, education.start.month or 0)
            end_tuple = (education.end.year, education.end.month or 0)
            if start_tuple > end_tuple:
                issues.append(
                    f"Education entry {education_index} has a start date later than its end date."
                )

    for training_index, training in enumerate(education_skills.training, start=1):
        if training.start and training.end:
            start_tuple = (training.start.year, training.start.month or 0)
            end_tuple = (training.end.year, training.end.month or 0)
            if start_tuple > end_tuple:
                issues.append(
                    f"Training entry {training_index} has a start date later than its end date."
                )

    return issues


def _validate_resume_validation_guardrail(task_output: object) -> tuple[bool, Any]:
    try:
        result = _load_task_output_model(task_output, ResumeValidationResult)
    except (ValidationError, ValueError) as exc:
        return (False, f"Return a valid ResumeValidationResult object. {exc}")

    if not result.reason.strip():
        return (
            False,
            "Populate the reason field with one short, evidence-based explanation.",
        )
    return (True, result)


def _validate_profile_extraction_guardrail(task_output: object) -> tuple[bool, Any]:
    try:
        profile = _load_task_output_model(task_output, ComprehensiveCvProfile)
    except (ValidationError, ValueError) as exc:
        return (
            False,
            "Return a valid ComprehensiveCvProfile object that matches the schema exactly. "
            f"{exc}",
        )

    issues = _validate_profile_quality(profile)
    if issues:
        return (False, " ".join(issues))
    return (True, profile)


def _validate_curated_markdown(
    markdown: str,
    *,
    candidate_id: str,
    source_file: str,
) -> list[str]:
    issues: list[str] = []
    stripped = markdown.strip()

    if not stripped.startswith("---"):
        issues.append("The document must begin with YAML front matter.")

    required_metadata = (
        "record_type: candidate_resume",
        f"candidate_id: {json.dumps(candidate_id)}",
        f"source_file: {json.dumps(source_file)}",
    )
    for metadata in required_metadata:
        if metadata not in stripped:
            issues.append(f"Missing required front-matter field: {metadata}.")

    heading_positions: list[int] = []
    for heading in _REQUIRED_MARKDOWN_HEADINGS:
        position = stripped.find(heading)
        if position < 0:
            issues.append(f"Missing required section heading: {heading}.")
            continue
        heading_positions.append(position)
    if heading_positions and heading_positions != sorted(heading_positions):
        issues.append("Keep the required H2 headings in the specified order.")

    forbidden_fragments = (
        "```",
        "Structured profile JSON begins:",
        "Safe deterministic draft begins:",
    )
    for fragment in forbidden_fragments:
        if fragment in stripped:
            issues.append(f"Remove forbidden content from the curated markdown: {fragment}")

    return issues


def _build_markdown_guardrail(
    *, candidate_id: str, source_file: str
):
    def _guardrail(task_output: object) -> tuple[bool, Any]:
        markdown = getattr(task_output, "raw", None)
        if not isinstance(markdown, str) or not markdown.strip():
            return (False, "Return the curated markdown document only.")

        issues = _validate_curated_markdown(
            markdown,
            candidate_id=candidate_id,
            source_file=source_file,
        )
        if issues:
            return (False, " ".join(issues))
        return (True, markdown)

    return _guardrail


def _build_llm():
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


class CvExtractionCrew:
    def __init__(self, *, run_limits: CrewAIRunLimits | None = None) -> None:
        # Instrumentation must be registered before any Agent or Crew is created.
        initialize_deepeval()
        initialize_phoenix()
        self.llm = _build_llm()
        self._token_usage = {field: 0 for field in _TOKEN_USAGE_FIELDS}
        self._run_limiter = CrewAIRunLimiter(
            limits=run_limits,
            pricing=_build_run_pricing(),
        )

    @property
    def token_usage(self) -> dict[str, int]:
        """Aggregated CrewAI usage for every kickoff in this extraction flow."""

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
        self._record_token_usage(crew_output)
        self._run_limiter.assert_within_limits(self._token_usage, operation=operation)
        return crew_output

    def _bounded_execution_time(self, default_seconds: int) -> int:
        remaining_seconds = self._run_limiter.remaining_latency_seconds
        if remaining_seconds is None:
            return default_seconds
        return max(1, min(default_seconds, int(remaining_seconds)))

    def validate_resume(self, prompt: str) -> ResumeValidationResult:
        if self.llm is None:
            document_text = prompt
            start_marker = "Document text begins:\n---\n"
            end_marker = "\n---\nDocument text ends."
            if start_marker in prompt:
                document_text = prompt.split(start_marker, 1)[1].split(end_marker, 1)[0]

            lowered = document_text.lower()
            section_signals = sum(
                token in lowered
                for token in (
                    "experience",
                    "employment",
                    "work history",
                    "education",
                    "qualification",
                    "skills",
                    "projects",
                    "certification",
                )
            )
            contact_signals = "@" in document_text or any(
                token in lowered
                for token in ("linkedin.com/", "github.com/", "phone", "mobile")
            )
            is_resume = section_signals >= 2 or (
                section_signals >= 1 and contact_signals
            )
            return ResumeValidationResult(
                is_resume=is_resume,
                reason=(
                    "Fallback validation found multiple resume-specific sections or contact details."
                    if is_resume
                    else "Fallback validation found insufficient candidate-specific resume structure."
                ),
            )

        validator = Agent(
            role="Resume Validator",
            goal="Decide whether uploaded text is a resume or CV before extraction.",
            backstory="You are good at spotting resume structure and distinguishing it from unrelated documents.",
            llm=self.llm,
            max_execution_time=self._bounded_execution_time(60),
            verbose=False,
        )
        task = Task(
            description=prompt,
            expected_output=(
                "A ResumeValidationResult with is_resume set to true or false and one short, "
                "evidence-based reason."
            ),
            agent=validator,
            output_pydantic=ResumeValidationResult,
            guardrail=_validate_resume_validation_guardrail,
            guardrail_max_retries=2,
        )
        crew = Crew(
            agents=[validator], tasks=[task], process=Process.sequential, verbose=False
        )
        self._kickoff_with_limits(crew, operation="resume validation")
        return task.output.pydantic or ResumeValidationResult(
            is_resume=False,
            reason="CrewAI validation did not return structured output.",
        )

    def extract_profile(self, prompt: str) -> ComprehensiveCvProfile:
        if self.llm is None:
            return ComprehensiveCvProfile(
                extraction_notes=[
                    "Structured extraction was not run because OPENAI_API_KEY is not configured."
                ],
            )

        extractor = Agent(
            role="CV Extraction Specialist",
            goal="Convert resume text into a clean, structured candidate profile.",
            backstory="You extract hiring-relevant fields carefully and avoid fabricating missing details.",
            llm=self.llm,
            max_execution_time=self._bounded_execution_time(90),
            verbose=False,
        )
        task = Task(
            description=prompt,
            expected_output=(
                "One complete ComprehensiveCvProfile matching the target schema exactly. "
                "All facts must be grounded in the CV; missing values use schema defaults, "
                "dates use year/month objects, and material ambiguities go in extraction_notes."
            ),
            agent=extractor,
            output_pydantic=ComprehensiveCvProfile,
            guardrail=_validate_profile_extraction_guardrail,
            guardrail_max_retries=2,
        )
        crew = Crew(
            agents=[extractor], tasks=[task], process=Process.sequential, verbose=False
        )
        self._kickoff_with_limits(crew, operation="structured profile extraction")
        return task.output.pydantic or ComprehensiveCvProfile(
            extraction_notes=["CrewAI extraction did not return structured output."]
        )

    def curate_profile_markdown(
        self,
        profile: ComprehensiveCvProfile,
        *,
        candidate_id: str,
        source_file: str,
    ) -> str:
        """Create the agent-facing candidate record from the typed profile."""

        markdown_draft = render_cv_markdown(
            profile,
            candidate_id=candidate_id,
            source_file=source_file,
        )
        if self.llm is None:
            return markdown_draft

        curator = Agent(
            role="Recruitment Knowledge Curator",
            goal=(
                "Turn verified candidate profiles into consistent, highly navigable "
                "Markdown knowledge records without introducing new facts."
            ),
            backstory=(
                "You are an information architect for recruitment teams. You preserve "
                "source fidelity while making candidate records easy for other agents to scan."
            ),
            llm=self.llm,
            max_iter=8,
            max_execution_time=self._bounded_execution_time(120),
            allow_delegation=False,
            verbose=False,
        )
        task = Task(
            description=CV_MARKDOWN_PROMPT.format(
                candidate_id=candidate_id,
                source_file=source_file,
                profile_json=json.dumps(profile.model_dump(mode="json"), indent=2),
                markdown_draft=markdown_draft,
            ),
            expected_output=(
                "One standalone Markdown candidate record with YAML front matter and the "
                "nine required H2 sections, containing no facts absent from the profile."
            ),
            agent=curator,
            markdown=True,
            guardrail=_build_markdown_guardrail(
                candidate_id=candidate_id,
                source_file=source_file,
            ),
            guardrail_max_retries=2,
        )
        crew = Crew(
            agents=[curator], tasks=[task], process=Process.sequential, verbose=False
        )
        self._kickoff_with_limits(crew, operation="structured markdown curation")

        curated = (task.output.raw if task.output else "").strip()
        if _validate_curated_markdown(
            curated,
            candidate_id=candidate_id,
            source_file=source_file,
        ):
            return markdown_draft
        return curated + "\n"
