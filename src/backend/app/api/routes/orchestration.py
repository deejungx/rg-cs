from fastapi import APIRouter, File, Form, UploadFile

from app.api.deps import upload_service
from src.ai.pipelines.candidate_analysis_flow import run_candidate_analysis
from src.shared.schemas import CandidateAnalysisResponse

router = APIRouter(prefix="/api/orchestration", tags=["orchestration"])


@router.post("/analyze", response_model=CandidateAnalysisResponse)
async def analyze_candidate(
    file: UploadFile = File(...),
    job_title: str = Form(...),
    job_description: str = Form(""),
    company_name: str = Form(""),
    location: str = Form(""),
    skills_csv: str = Form(""),
) -> CandidateAnalysisResponse:
    upload = await upload_service.save_cv(file)
    return run_candidate_analysis(
        candidate_id=upload["candidate_id"],
        source_path=upload["absolute_path"],
        filename=upload["filename"],
        content_type=upload["content_type"],
        job_title=job_title,
        job_description=job_description,
        company_name=company_name,
        location=location,
        skills_csv=skills_csv,
    )
