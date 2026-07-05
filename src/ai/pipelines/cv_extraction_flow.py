from pathlib import Path

from crewai.flow.flow import Flow, listen, start
from pydantic import BaseModel, Field

from app.services.file_parser import file_parser_service
from app.services.workspace_service import workspace_service
from src.ai.crews.cv_extraction_crew import CvExtractionCrew
from src.ai.prompts.cv_extraction import CV_EXTRACTION_PROMPT, RESUME_VALIDATION_PROMPT
from src.ai.tracing.phoenix import flush_phoenix, traced_operation
from src.ai.tracing.run_logger import append_log
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


class CvExtractionFlow(Flow[CvExtractionState]):
    def __init__(
        self, *, candidate_id: str, source_path: str, filename: str, content_type: str
    ) -> None:
        super().__init__()
        self.state.candidate_id = candidate_id
        self.state.source_path = source_path
        self.state.filename = filename
        self.state.content_type = content_type
        self.crew = CvExtractionCrew()

    @start()
    def parse_document(self) -> DocumentParseResult:
        parsed = file_parser_service.parse_path(Path(self.state.source_path))
        self.state.parsed = parsed
        return parsed

    @listen(parse_document)
    def validate_document(self, parsed: DocumentParseResult) -> ResumeValidationResult:
        validation = self.crew.validate_resume(
            RESUME_VALIDATION_PROMPT.format(document_text=parsed.text[:12000])
        )
        self.state.validation = validation
        return validation

    @listen(validate_document)
    def extract_structured_profile(
        self, validation: ResumeValidationResult
    ) -> ComprehensiveCvProfile:
        if not validation.is_resume:
            profile = ComprehensiveCvProfile(
                extraction_notes=[
                    validation.reason or "Document did not validate as a CV."
                ]
            )
            self.state.structured_profile = profile
            return profile

        profile = self.crew.extract_profile(
            CV_EXTRACTION_PROMPT.format(document_text=self.state.parsed.text[:20000])
        )
        self.state.structured_profile = profile
        return profile

    @listen(extract_structured_profile)
    def curate_structured_markdown(self, profile: ComprehensiveCvProfile) -> str:
        markdown = self.crew.curate_profile_markdown(
            profile,
            candidate_id=self.state.candidate_id,
            source_file=self.state.filename,
        )
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
    *, candidate_id: str, source_path: str, filename: str, content_type: str
) -> dict[str, object]:
    try:
        with traced_operation(
            "cv_extraction_flow",
            {
                "candidate_id": candidate_id,
                "source_file": filename,
                "content_type": content_type,
            },
        ):
            flow = CvExtractionFlow(
                candidate_id=candidate_id,
                source_path=source_path,
                filename=filename,
                content_type=content_type,
            )
            return flow.kickoff()
    finally:
        flush_phoenix()
