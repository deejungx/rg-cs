import json
import time
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.api.deps import task_queue, upload_service
from app.services.orchestration_progress_service import (
    orchestration_progress_service,
)
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


@router.post("/runs")
async def create_candidate_analysis_run(
    file: UploadFile = File(...),
    job_title: str = Form(...),
    job_description: str = Form(""),
    company_name: str = Form(""),
    location: str = Form(""),
    skills_csv: str = Form(""),
) -> dict[str, str]:
    upload = await upload_service.save_cv(file)
    run_id = f"analysis-{uuid4()}"
    orchestration_progress_service.create_run(
        run_id=run_id,
        candidate_id=upload["candidate_id"],
        filename=upload["filename"],
    )
    task = task_queue.enqueue_candidate_analysis(
        run_id=run_id,
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
    orchestration_progress_service.set_status(
        run_id,
        status="queued",
        task_id=task.id,
    )
    orchestration_progress_service.publish_event(
        run_id,
        {
            "run_id": run_id,
            "type": "run_queued",
            "label": "candidate_analysis",
            "stage": "candidate_analysis",
            "message": "Run queued and waiting for a worker.",
            "task_id": task.id,
        },
    )
    return {"run_id": run_id, "task_id": task.id, "candidate_id": upload["candidate_id"]}


@router.get("/runs/{run_id}")
def get_candidate_analysis_run(run_id: str) -> dict[str, object]:
    payload = orchestration_progress_service.get_run(run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"Unknown run id: {run_id}")
    return payload


@router.get("/runs/{run_id}/events")
def stream_candidate_analysis_events(run_id: str) -> StreamingResponse:
    if orchestration_progress_service.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown run id: {run_id}")

    def event_stream():
        terminal = {"completed", "failed"}
        emitted_sequences: set[int] = set()

        for event in orchestration_progress_service.get_events(run_id):
            emitted_sequences.add(event["sequence"])
            yield f"id: {event['sequence']}\ndata: {json.dumps(event)}\n\n"

        run_payload = orchestration_progress_service.get_run(run_id)
        if run_payload and run_payload["status"] in terminal:
            return

        pubsub = orchestration_progress_service.subscribe(run_id)
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
                    run_payload = orchestration_progress_service.get_run(run_id)
                    if run_payload and run_payload["status"] in terminal:
                        break
                else:
                    yield ": keepalive\n\n"
                    run_payload = orchestration_progress_service.get_run(run_id)
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
