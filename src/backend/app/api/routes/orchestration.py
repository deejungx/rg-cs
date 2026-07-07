import json
import time
from uuid import uuid4

from pydantic import BaseModel
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.api.deps import task_queue, upload_service, workspace_service
from app.services.orchestration_progress_service import (
    orchestration_progress_service,
)
from src.ai.events.progress_listener import ensure_progress_listener
from src.ai.events.runtime_context import current_run_id
from src.ai.pipelines.candidate_analysis_flow import (
    _build_vacancy_data,
    _profile_to_cv_data,
    run_candidate_analysis,
)
from src.ai.pipelines.cv_matching_flow import run_cv_matching_flow
from src.shared.schemas import (
    CVMatchingRequest,
    CandidateAnalysisResponse,
    ComprehensiveCvProfile,
)

router = APIRouter(prefix="/api/orchestration", tags=["orchestration"])


class StoredCandidateMatchRequest(BaseModel):
    candidate_id: str
    job_title: str
    job_description: str = ""
    company_name: str = ""
    location: str = ""
    skills_csv: str = ""


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


def _run_stored_candidate_match(
    *,
    run_id: str,
    request: StoredCandidateMatchRequest,
    profile_json: str,
) -> None:
    ensure_progress_listener()
    run_token = current_run_id.set(run_id)
    try:
        orchestration_progress_service.set_status(run_id, status="running")
        orchestration_progress_service.publish_event(
            run_id,
            {
                "run_id": run_id,
                "type": "run_started",
                "label": "stored_candidate_match",
                "stage": "stored_candidate_match",
                "message": "Started match analysis for stored candidate.",
            },
        )
        profile = ComprehensiveCvProfile.model_validate_json(profile_json)
        vacancy = _build_vacancy_data(
            title=request.job_title,
            description=request.job_description,
            company_name=request.company_name,
            location=request.location,
            skills_csv=request.skills_csv,
        )
        matching_payload = run_cv_matching_flow(
            CVMatchingRequest(
                cv_data=_profile_to_cv_data(
                    candidate_id=request.candidate_id,
                    profile=profile,
                ),
                vacancy_data=vacancy,
            )
        )
        result = {
            "analysis_id": run_id,
            "candidate_id": request.candidate_id,
            "extraction": None,
            "vacancy": vacancy.model_dump(mode="json"),
            "matching": matching_payload,
            "trace": [],
        }
        orchestration_progress_service.set_status(run_id, status="completed", result=result)
        orchestration_progress_service.publish_event(
            run_id,
            {
                "run_id": run_id,
                "type": "run_completed",
                "label": "stored_candidate_match",
                "stage": "stored_candidate_match",
                "message": "Match analysis completed.",
            },
        )
    except Exception as exc:
        orchestration_progress_service.set_status(run_id, status="failed", error=str(exc))
        orchestration_progress_service.publish_event(
            run_id,
            {
                "run_id": run_id,
                "type": "run_failed",
                "label": "stored_candidate_match",
                "stage": "stored_candidate_match",
                "error": str(exc),
                "message": "Match analysis failed.",
            },
        )
    finally:
        current_run_id.reset(run_token)


@router.post("/stored-candidate-runs")
def create_stored_candidate_match_run(
    request: StoredCandidateMatchRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    structured_path = f"candidates/{request.candidate_id}/resume_structured.json"
    try:
        profile_payload = workspace_service.read_workspace_path(structured_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown candidate id: {request.candidate_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    run_id = f"match-{uuid4()}"
    orchestration_progress_service.create_run(
        run_id=run_id,
        candidate_id=request.candidate_id,
        filename="stored_candidate",
    )
    orchestration_progress_service.set_status(run_id, status="queued")
    orchestration_progress_service.publish_event(
        run_id,
        {
            "run_id": run_id,
            "type": "run_queued",
            "label": "stored_candidate_match",
            "stage": "stored_candidate_match",
            "message": "Stored candidate match analysis queued.",
        },
    )
    background_tasks.add_task(
        _run_stored_candidate_match,
        run_id=run_id,
        request=request,
        profile_json=str(profile_payload["content"]),
    )
    return {"run_id": run_id, "task_id": "", "candidate_id": request.candidate_id}


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
