from celery.result import AsyncResult
from fastapi import APIRouter, File, UploadFile

from app.api.deps import task_queue, upload_service
from app.workers.celery_app import celery_app

router = APIRouter(prefix="/api/cv", tags=["cv"])


@router.post("/extract")
async def extract_cv(file: UploadFile = File(...)) -> dict[str, str]:
    upload = await upload_service.save_cv(file)
    task = task_queue.enqueue_cv_extraction(
        candidate_id=upload["candidate_id"],
        source_path=upload["absolute_path"],
        filename=upload["filename"],
        content_type=upload["content_type"],
    )
    return {
        "task_id": task.id,
        "state": task.state,
        "candidate_id": upload["candidate_id"],
    }


@router.get("/tasks/{task_id}")
def get_cv_task(task_id: str) -> dict[str, object]:
    result = AsyncResult(task_id, app=celery_app)
    payload: dict[str, object] = {"task_id": task_id, "state": result.state}
    if result.successful():
        payload["result"] = result.result
    elif result.failed():
        payload["error"] = str(result.result)
    return payload
