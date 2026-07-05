from fastapi import APIRouter

from app.api.deps import task_queue

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, object]:
    return {"status": "ok", "broker": task_queue.health()}
