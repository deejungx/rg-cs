from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.shared.schemas.cv import CvExtractionResponse
from src.shared.schemas.matching import CVMatchingResponse, VacancyData


class OrchestrationBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TraceContract(OrchestrationBaseModel):
    name: str
    summary: str


class TraceValidation(OrchestrationBaseModel):
    ok: bool = True
    message: str = ""


class ExecutionTraceStep(OrchestrationBaseModel):
    step: str
    agent: str
    status: Literal["completed", "skipped", "failed"]
    input_contract: TraceContract
    output_contract: TraceContract
    validation: TraceValidation = Field(default_factory=TraceValidation)
    started_at: str
    ended_at: str
    model_mode: Literal["live", "mock"]


class CandidateAnalysisResponse(OrchestrationBaseModel):
    analysis_id: str
    candidate_id: str
    model_provider: str
    model_mode: Literal["live", "mock"]
    provider_reason: str
    extraction: CvExtractionResponse
    vacancy: VacancyData
    matching: CVMatchingResponse | None = None
    trace: list[ExecutionTraceStep] = Field(default_factory=list)
