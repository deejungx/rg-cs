import json
import time
from uuid import uuid4

from celery.result import AsyncResult
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.api.deps import task_queue, upload_service, workspace_service
from app.services.orchestration_progress_service import orchestration_progress_service
from app.workers.celery_app import celery_app

router = APIRouter(prefix="/api/cv", tags=["cv"])


@router.post("/extract")
async def extract_cv(file: UploadFile = File(...)) -> dict[str, str]:
    upload = await upload_service.save_cv(file)
    task_id = f"extraction-{uuid4()}"
    orchestration_progress_service.create_run(
        run_id=task_id,
        candidate_id=upload["candidate_id"],
        filename=upload["filename"],
    )
    task = task_queue.enqueue_cv_extraction(
        task_id=task_id,
        candidate_id=upload["candidate_id"],
        source_path=upload["absolute_path"],
        filename=upload["filename"],
        content_type=upload["content_type"],
    )
    orchestration_progress_service.set_status(task_id, status="queued", task_id=task.id)
    orchestration_progress_service.publish_event(
        task_id,
        {
            "run_id": task_id,
            "type": "run_queued",
            "label": "resume_extraction",
            "stage": "resume_extraction",
            "message": "Resume extraction queued.",
            "task_id": task.id,
        },
    )
    return {
        "task_id": task.id,
        "state": task.state,
        "candidate_id": upload["candidate_id"],
    }


def _read_artifacts(result: dict[str, object]) -> dict[str, object]:
    artifacts = result.get("artifacts")
    if not isinstance(artifacts, dict):
        return {}

    payload: dict[str, object] = {}
    json_path = artifacts.get("structured_json_path")
    markdown_path = artifacts.get("structured_markdown_path")
    if isinstance(json_path, str):
        try:
            payload["structured_json"] = workspace_service.read_workspace_path(json_path)["content"]
        except (FileNotFoundError, ValueError):
            payload["structured_json"] = ""
    if isinstance(markdown_path, str):
        try:
            payload["structured_markdown"] = workspace_service.read_workspace_path(markdown_path)["content"]
        except (FileNotFoundError, ValueError):
            payload["structured_markdown"] = ""
    return payload


@router.get("/tasks/{task_id}")
def get_cv_task(task_id: str) -> dict[str, object]:
    result = AsyncResult(task_id, app=celery_app)
    payload: dict[str, object] = {"task_id": task_id, "state": result.state}
    if result.successful():
        payload["result"] = result.result
        if isinstance(result.result, dict):
            payload["artifacts"] = _read_artifacts(result.result)
    elif result.failed():
        payload["error"] = str(result.result)
    return payload


@router.get("/tasks/{task_id}/events")
def stream_cv_task_events(task_id: str) -> StreamingResponse:
    if orchestration_progress_service.get_run(task_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown task id: {task_id}")

    def event_stream():
        terminal = {"completed", "failed"}
        emitted_sequences: set[int] = set()

        for event in orchestration_progress_service.get_events(task_id):
            emitted_sequences.add(event["sequence"])
            yield f"id: {event['sequence']}\ndata: {json.dumps(event)}\n\n"

        run_payload = orchestration_progress_service.get_run(task_id)
        if run_payload and run_payload["status"] in terminal:
            return

        pubsub = orchestration_progress_service.subscribe(task_id)
        try:
            while True:
                message = pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )
                if message and message["type"] == "message":
                    event = json.loads(message["data"])
                    sequence = int(event["sequence"])
                    if sequence in emitted_sequences:
                        continue
                    emitted_sequences.add(sequence)
                    yield f"id: {sequence}\ndata: {json.dumps(event)}\n\n"
                    run_payload = orchestration_progress_service.get_run(task_id)
                    if run_payload and run_payload["status"] in terminal:
                        break
                else:
                    yield ": keepalive\n\n"
                    run_payload = orchestration_progress_service.get_run(task_id)
                    if run_payload and run_payload["status"] in terminal:
                        break
                    time.sleep(0.25)
        finally:
            pubsub.unsubscribe()
            pubsub.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
