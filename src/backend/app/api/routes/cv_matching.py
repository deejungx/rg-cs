from fastapi import APIRouter, HTTPException

from src.ai.pipelines.cv_matching_flow import run_cv_matching_flow
from src.shared.schemas import CVMatchingRequest, CVMatchingResponse

router = APIRouter(prefix="/api/cv-matching", tags=["cv-matching"])


@router.post("/analyze", response_model=CVMatchingResponse)
async def analyze_cv_match(request: CVMatchingRequest) -> CVMatchingResponse:
    try:
        result = run_cv_matching_flow(request)
        return CVMatchingResponse.model_validate(result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"CV matching failed: {exc}") from exc
