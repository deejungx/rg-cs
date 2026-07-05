import json

from crewai import Agent, Crew, Process, Task

from app.core.config import settings
from src.ai.formatters.cv_markdown import render_cv_markdown
from src.ai.prompts.cv_extraction import CV_MARKDOWN_PROMPT
from src.ai.tracing.phoenix import initialize_phoenix
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


def _build_llm():
    if not settings.openai_api_key:
        return None

    from crewai import LLM

    return LLM(
        model=f"openai/{settings.openai_model}",
        api_key=settings.openai_api_key,
        temperature=0.1,
    )


class CvExtractionCrew:
    def __init__(self) -> None:
        # Instrumentation must be registered before any Agent or Crew is created.
        initialize_phoenix()
        self.llm = _build_llm()
        self._token_usage = {field: 0 for field in _TOKEN_USAGE_FIELDS}

    @property
    def token_usage(self) -> dict[str, int]:
        """Aggregated CrewAI usage for every kickoff in this extraction flow."""

        return self._token_usage.copy()

    def _record_token_usage(self, crew_output: object) -> None:
        usage = getattr(crew_output, "token_usage", None)
        if usage is None:
            return
        values = usage.model_dump() if hasattr(usage, "model_dump") else {}
        for field in _TOKEN_USAGE_FIELDS:
            self._token_usage[field] += int(values.get(field, 0) or 0)

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
        )
        crew = Crew(
            agents=[validator], tasks=[task], process=Process.sequential, verbose=False
        )
        crew_output = crew.kickoff()
        self._record_token_usage(crew_output)
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
        )
        crew = Crew(
            agents=[extractor], tasks=[task], process=Process.sequential, verbose=False
        )
        crew_output = crew.kickoff()
        self._record_token_usage(crew_output)
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
            max_execution_time=120,
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
        )
        crew = Crew(
            agents=[curator], tasks=[task], process=Process.sequential, verbose=False
        )
        crew_output = crew.kickoff()
        self._record_token_usage(crew_output)

        curated = (task.output.raw if task.output else "").strip()
        required_headings = (
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
        required_metadata = (
            "record_type: candidate_resume",
            f"candidate_id: {json.dumps(candidate_id)}",
            f"source_file: {json.dumps(source_file)}",
        )
        if (
            not curated.startswith("---")
            or not all(heading in curated for heading in required_headings)
            or not all(metadata in curated for metadata in required_metadata)
        ):
            return markdown_draft
        return curated + "\n"
