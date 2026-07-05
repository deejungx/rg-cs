from fastapi import APIRouter, HTTPException

from app.api.deps import workspace_service

router = APIRouter(prefix="/api/workspace", tags=["workspace"])


@router.get("/{path:path}")
def read_workspace_file(path: str) -> dict[str, object]:
    try:
        return workspace_service.read_workspace_path(path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
