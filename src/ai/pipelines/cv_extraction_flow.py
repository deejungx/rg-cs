from pathlib import Path

from crewai.flow.flow import Flow, listen, start
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.file_parser import file_parser_service
from app.services.pii_redaction_service import pii_redaction_service
from app.services.workspace_service import workspace_service
from src.ai.events.runtime_context import current_stage
from src.ai.crews.cv_extraction_crew import CvExtractionCrew
from src.ai.prompts.cv_extraction import CV_EXTRACTION_PROMPT, RESUME_VALIDATION_PROMPT
from src.ai.tracing.phoenix import flush_phoenix, traced_operation
from src.ai.tracing.run_logger import append_log
from src.shared import CrewAIRunLimits
from src.shared.schemas import (
    CandidateArtifacts,
    ComprehensiveCvProfile,
    CvExtractionResponse,
    DocumentParseResult,
    ResumeValidationResult,
)


class CvExtractionState(BaseModel):
    candidate_id: str = ""
    source_path: str = ""
    filename: str = ""
    content_type: str = ""
    parsed: DocumentParseResult = Field(default_factory=DocumentParseResult)
    validation: ResumeValidationResult = Field(default_factory=ResumeValidationResult)
    structured_profile: ComprehensiveCvProfile | None = None
    structured_markdown: str = ""
    artifacts: CandidateArtifacts | None = None


class InvalidResumeError(ValueError):
    """Raised when validation determines the uploaded document is not a resume."""


class CvExtractionFlow(Flow[CvExtractionState]):
    def __init__(
        self,
        *,
        candidate_id: str,
        source_path: str,
        filename: str,
        content_type: str,
        run_limits: CrewAIRunLimits | None = None,
    ) -> None:
        super().__init__()
        self.state.candidate_id = candidate_id
        self.state.source_path = source_path
        self.state.filename = filename
        self.state.content_type = content_type
        self.crew = CvExtractionCrew(run_limits=run_limits)

    @start()
    def parse_document(self) -> DocumentParseResult:
        parsed = file_parser_service.parse_path(Path(self.state.source_path))
        parsed = pii_redaction_service.redact_parse_result(parsed)
        self.state.parsed = parsed
        return parsed

    @listen(parse_document)
    def validate_document(self, parsed: DocumentParseResult) -> ResumeValidationResult:
        stage_token = current_stage.set("validate_document")
        try:
            validation = self.crew.validate_resume(
                RESUME_VALIDATION_PROMPT.format(document_text=parsed.source_text[:12000])
            )
        finally:
            current_stage.reset(stage_token)
        self.state.validation = validation
        return validation

    @listen(validate_document)
    def extract_structured_profile(
        self, validation: ResumeValidationResult
    ) -> ComprehensiveCvProfile:
        if not validation.is_resume:
            reason = validation.reason or "The validation step did not identify resume content."
            raise InvalidResumeError(
                f"Uploaded document does not appear to be a resume. {reason}"
            )

        stage_token = current_stage.set("extract_structured_profile")
        try:
            profile = self.crew.extract_profile(
                CV_EXTRACTION_PROMPT.format(
                    document_text=self.state.parsed.source_text[:20000]
                )
            )
        finally:
            current_stage.reset(stage_token)
        self.state.structured_profile = profile
        return profile

    @listen(extract_structured_profile)
    def review_missing_fields(
        self, profile: ComprehensiveCvProfile
    ) -> ComprehensiveCvProfile:
        stage_token = current_stage.set("review_missing_fields")
        try:
            reviewed_profile = self.crew.review_missing_fields(profile)
        finally:
            current_stage.reset(stage_token)
        self.state.structured_profile = reviewed_profile
        return reviewed_profile

    @listen(review_missing_fields)
    def curate_structured_markdown(self, profile: ComprehensiveCvProfile) -> str:
        stage_token = current_stage.set("curate_structured_markdown")
        try:
            markdown = self.crew.curate_profile_markdown(
                profile,
                candidate_id=self.state.candidate_id,
                source_file=self.state.filename,
            )
        finally:
            current_stage.reset(stage_token)
        self.state.structured_markdown = markdown
        append_log(
            run_id=self.state.candidate_id,
            event={
                "stage": "resume_markdown_curation",
                "candidate_id": self.state.candidate_id,
            },
        )
        return markdown

    @listen(curate_structured_markdown)
    def persist_outputs(self, structured_markdown: str) -> dict[str, object]:
        if self.state.structured_profile is None:
            raise RuntimeError(
                "Cannot persist CV artifacts without a structured profile."
            )

        candidate_root = (
            workspace_service.workspace_dir / "candidates" / self.state.candidate_id
        )
        legacy_parsed_markdown = candidate_root / "resume_parsed.md"
        resume_markdown = candidate_root / "resume.md"
        structured_json = candidate_root / "resume_structured.json"
        trace_json = candidate_root / "traces" / "extraction_trace.json"

        artifacts = CandidateArtifacts(
            candidate_id=self.state.candidate_id,
            upload_path=str(
                Path(self.state.source_path).relative_to(
                    workspace_service.uploads_dir.parent
                )
            ),
            structured_markdown_path=str(
                resume_markdown.relative_to(workspace_service.workspace_dir)
            ),
            structured_json_path=str(
                structured_json.relative_to(workspace_service.workspace_dir)
            ),
            trace_path=str(trace_json.relative_to(workspace_service.workspace_dir)),
        )
        self.state.artifacts = artifacts

        with traced_operation(
            "cv_extraction.persist_outputs",
            {"candidate_id": self.state.candidate_id},
        ):
            legacy_parsed_markdown.unlink(missing_ok=True)
            workspace_service.write_text(resume_markdown, structured_markdown)
            workspace_service.write_json(
                structured_json,
                self.state.structured_profile.model_dump(mode="json"),
            )
            workspace_service.write_json(
                trace_json,
                {
                    "candidate_id": self.state.candidate_id,
                    "validation": self.state.validation.model_dump(),
                    "parser": self.state.parsed.model_dump(),
                    "token_usage": self.crew.token_usage,
                    "estimated_cost_usd": self.crew.estimated_cost_usd,
                    "elapsed_seconds": self.crew.elapsed_seconds,
                    "run_limits": self.crew.run_limits.model_dump(),
                    "structured_markdown_path": artifacts.structured_markdown_path,
                    "flow_state_id": self.state.id,
                },
            )

        append_log(
            run_id=self.state.candidate_id,
            event={
                "stage": "cv_extraction",
                "candidate_id": self.state.candidate_id,
                "validated": self.state.validation.is_resume,
                "token_usage": self.crew.token_usage,
                "estimated_cost_usd": self.crew.estimated_cost_usd,
                "elapsed_seconds": self.crew.elapsed_seconds,
            },
        )

        response = CvExtractionResponse(
            candidate_id=self.state.candidate_id,
            validation=self.state.validation,
            parsed=self.state.parsed,
            structured_profile=self.state.structured_profile,
            artifacts=artifacts,
        )
        return response.model_dump()


def run_cv_extraction_flow(
    *,
    candidate_id: str,
    source_path: str,
    filename: str,
    content_type: str,
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
    try:
        with traced_operation(
            "cv_extraction_flow",
            {
                "candidate_id": candidate_id,
                "source_file": filename,
                "content_type": content_type,
                "run_limits": run_limits.model_dump(),
            },
        ):
            flow = CvExtractionFlow(
                candidate_id=candidate_id,
                source_path=source_path,
                filename=filename,
                content_type=content_type,
                run_limits=run_limits,
            )
            return flow.kickoff()
    finally:
        flush_phoenix()
