from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.services.sample_data_service import sample_data_service

router = APIRouter(prefix="/api/samples", tags=["samples"])


@router.get("")
def list_samples() -> dict[str, object]:
    return {"samples": sample_data_service.list_samples()}


@router.get("/{sample_id}/resume")
def download_sample_resume(sample_id: str) -> FileResponse:
    try:
        path = sample_data_service.get_resume_path(sample_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path=path, filename=path.name)
