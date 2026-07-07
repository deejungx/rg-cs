import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.deps import workspace_service
from app.services.orchestration_progress_service import orchestration_progress_service
from src.ai.pipelines.job_opening_flow import render_job_opening_markdown, run_job_opening_flow
from src.shared.schemas import (
    AnnotatedJobOpening,
    JobOpeningExtractionRequest,
    JobOpeningExtractionResponse,
)

router = APIRouter(prefix="/api/recruitment", tags=["recruitment"])


class JobOpeningRequest(BaseModel):
    title: str
    company_name: str = ""
    location: str = ""
    employment_type: str = ""
    skills_csv: str = ""
    description: str = ""


class JobOpeningStatusRequest(BaseModel):
    status: Literal["active", "inactive"]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:72] or "job-opening"


def _job_root() -> Path:
    return workspace_service.workspace_dir / "job_openings"


def _job_markdown(payload: dict[str, Any]) -> str:
    skills = payload.get("skills", [])
    skill_lines = "\n".join(f"- {skill}" for skill in skills) or "- Not specified"
    return (
        f"# {payload['title']}\n\n"
        f"**Status:** {payload.get('status') or 'active'}\n\n"
        f"**Company:** {payload.get('company_name') or 'Not specified'}\n\n"
        f"**Location:** {payload.get('location') or 'Not specified'}\n\n"
        f"**Employment type:** {payload.get('employment_type') or 'Not specified'}\n\n"
        "## Skills\n\n"
        f"{skill_lines}\n\n"
        "## Description\n\n"
        f"{payload.get('description') or 'No description provided.'}\n"
    )


def _markdown_with_status(markdown: str, status: str) -> str:
    status_line = f"**Status:** {status}"
    if re.search(r"^\*\*Status:\*\* .+$", markdown, flags=re.MULTILINE):
        return re.sub(r"^\*\*Status:\*\* .+$", status_line, markdown, count=1, flags=re.MULTILINE)
    match = re.match(r"^(# .+\n)", markdown)
    if match:
        return f"{match.group(1)}\n{status_line}\n{markdown[match.end():]}"
    return f"{status_line}\n\n{markdown}"


def _persist_job(job: AnnotatedJobOpening, markdown: str) -> JobOpeningExtractionResponse:
    directory = _job_root() / job.id
    job_payload = job.model_dump(mode="json")
    job_payload["status"] = "active"
    job_payload["json_path"] = f"job_openings/{job.id}/job_opening.json"
    job_payload["markdown_path"] = f"job_openings/{job.id}/job_opening.md"
    workspace_service.write_json(directory / "job_opening.json", job_payload)
    workspace_service.write_text(directory / "job_opening.md", _markdown_with_status(markdown, job_payload["status"]))
    return JobOpeningExtractionResponse(
        job_opening=job,
        markdown=markdown,
        json_path=job_payload["json_path"],
        markdown_path=job_payload["markdown_path"],
    )


def _publish_job_step(run_id: str, event_type: str, label: str, message: str = "") -> None:
    orchestration_progress_service.publish_event(
        run_id,
        {
            "run_id": run_id,
            "type": event_type,
            "label": label,
            "stage": label,
            "message": message,
        },
    )


def _run_job_opening_extraction(run_id: str, request: JobOpeningExtractionRequest) -> None:
    try:
        orchestration_progress_service.set_status(run_id, status="running")
        _publish_job_step(run_id, "run_started", "job_opening_curation", "Job opening curation started.")

        if request.source_type == "website":
            _publish_job_step(run_id, "step_started", "fetch_source_content", "Fetching website content.")
        else:
            _publish_job_step(run_id, "step_started", "read_pasted_text", "Reading pasted job description.")

        if request.source_type == "website":
            _publish_job_step(run_id, "step_completed", "fetch_source_content", "Website content fetched and cleaned.")
        else:
            _publish_job_step(run_id, "step_completed", "read_pasted_text", "Pasted job description received.")

        _publish_job_step(run_id, "step_started", "extract_structured_job", "Extracting structured job opening.")
        job, markdown = run_job_opening_flow(
            source_type=request.source_type,
            content=request.content,
        )
        _publish_job_step(run_id, "step_completed", "extract_structured_job", "Structured job opening extracted.")

        _publish_job_step(run_id, "step_started", "quality_guardrail", "Checking extraction quality.")
        if job.metadata.missing_fields or job.metadata.quality_warnings:
            message = "Quality metadata generated with missing fields or warnings."
        else:
            message = "Quality guardrail passed with no warnings."
        _publish_job_step(run_id, "step_completed", "quality_guardrail", message)

        _publish_job_step(run_id, "step_started", "persist_job_opening", "Persisting job artifacts.")
        response = _persist_job(job, markdown)
        _publish_job_step(run_id, "step_completed", "persist_job_opening", "Job artifacts persisted.")

        orchestration_progress_service.set_status(
            run_id,
            status="completed",
            result=response.model_dump(mode="json"),
        )
        _publish_job_step(run_id, "run_completed", "job_opening_curation", "Job opening curation completed.")
    except Exception as exc:
        orchestration_progress_service.set_status(run_id, status="failed", error=str(exc))
        _publish_job_step(
            run_id,
            "run_failed",
            "job_opening_curation",
            "Job opening curation failed.",
        )


def _read_job(path: Path) -> dict[str, Any] | None:
    json_path = path / "job_opening.json"
    if not json_path.exists():
        return None
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    payload.setdefault("status", "active")
    return payload


def _list_jobs() -> list[dict[str, Any]]:
    root = _job_root()
    if not root.exists():
        return []
    jobs = [_read_job(path) for path in root.iterdir() if path.is_dir()]
    return sorted(
        [job for job in jobs if job is not None],
        key=lambda item: str(item.get("created_at", "")),
        reverse=True,
    )


def _job_directory(job_id: str) -> Path:
    if "/" in job_id or "\\" in job_id or job_id in {"", ".", ".."}:
        raise HTTPException(status_code=404, detail=f"Unknown job opening id: {job_id}")
    return _job_root() / job_id


def _get_job(job_id: str) -> dict[str, Any]:
    payload = _read_job(_job_directory(job_id))
    if payload is None:
        raise HTTPException(status_code=404, detail=f"Unknown job opening id: {job_id}")
    return payload


def _run_totals(run_id: str) -> tuple[int, float]:
    tokens = 0
    cost = 0.0
    try:
        events = orchestration_progress_service.get_events(run_id)
    except Exception:
        return tokens, cost
    for event in events:
        usage = event.get("usage") or {}
        tokens += int(usage.get("total_tokens") or event.get("total_tokens_consumed") or 0)
        if isinstance(event.get("estimated_cost_usd"), int | float):
            cost += float(event["estimated_cost_usd"])
    return tokens, cost


def _recent_runs() -> list[dict[str, Any]]:
    try:
        keys = orchestration_progress_service.client.keys("orchestration:run:*")
    except Exception:
        return []

    runs: list[dict[str, Any]] = []
    for key in keys:
        if key.endswith(":events") or key.endswith(":seq") or key.endswith(":channel"):
            continue
        run_id = key.rsplit(":", 1)[-1]
        try:
            run = orchestration_progress_service.get_run(run_id)
        except Exception:
            run = None
        if not run:
            continue
        tokens, cost = _run_totals(run_id)
        runs.append(
            {
                "run_id": run["run_id"],
                "candidate_id": run.get("candidate_id", ""),
                "filename": run.get("filename", ""),
                "status": run.get("status", "unknown"),
                "created_at": run.get("created_at", ""),
                "updated_at": run.get("updated_at", ""),
                "tokens": tokens,
                "estimated_cost_usd": cost,
            }
        )
    return sorted(runs, key=lambda item: str(item.get("created_at", "")), reverse=True)


def _count_dirs(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for item in path.iterdir() if item.is_dir())


def _candidate_summary(path: Path) -> dict[str, Any] | None:
    structured_json = path / "resume_structured.json"
    markdown_path = path / "resume.md"
    if not structured_json.exists():
        return None

    profile = json.loads(structured_json.read_text(encoding="utf-8"))
    personal = profile.get("personal_info") or {}
    professional = profile.get("professional_experience") or {}
    education_skills = profile.get("education_skills") or {}
    full_name = " ".join(
        part
        for part in (
            str(personal.get("firstname") or "").strip(),
            str(personal.get("lastname") or "").strip(),
        )
        if part
    )
    skills = education_skills.get("skills") or []
    work = professional.get("work") or []
    projects = professional.get("projects") or []
    return {
        "candidate_id": path.name,
        "full_name": full_name or "Unnamed candidate",
        "primary_designation": professional.get("primary_designation") or "",
        "primary_industry": professional.get("primary_industry") or "",
        "location": personal.get("address") or "",
        "education_qualification": education_skills.get("education_qualification") or "",
        "skills": skills[:8],
        "skill_count": len(skills),
        "experience_count": len(work),
        "project_count": len(projects),
        "updated_at": datetime.fromtimestamp(
            structured_json.stat().st_mtime,
            tz=UTC,
        ).isoformat(),
        "structured_json_path": f"candidates/{path.name}/resume_structured.json",
        "structured_markdown_path": (
            f"candidates/{path.name}/resume.md" if markdown_path.exists() else ""
        ),
    }


def _list_candidates() -> list[dict[str, Any]]:
    root = workspace_service.workspace_dir / "candidates"
    if not root.exists():
        return []
    candidates = [_candidate_summary(path) for path in root.iterdir() if path.is_dir()]
    return sorted(
        [candidate for candidate in candidates if candidate is not None],
        key=lambda item: str(item.get("updated_at", "")),
        reverse=True,
    )


@router.get("/dashboard")
def dashboard() -> dict[str, Any]:
    runs = _recent_runs()
    successful = sum(1 for run in runs if run["status"] == "completed")
    failed = sum(1 for run in runs if run["status"] == "failed")
    total_tokens = sum(run["tokens"] for run in runs)
    candidates = len(_list_candidates())
    jobs = _list_jobs()
    return {
        "workflow_count": 3,
        "agent_count": 5,
        "runs_total": len(runs),
        "runs_successful": successful,
        "runs_failed": failed,
        "tokens_consumed": total_tokens,
        "candidates_total": candidates,
        "job_openings_total": len(jobs),
        "active_job_openings": sum(1 for job in jobs if job.get("status", "active") == "active"),
        "recent_runs": runs[:20],
        "workflows": [
            {"id": "resume-extraction", "name": "Resume Extraction", "status": "ready"},
            {"id": "job-openings", "name": "Job Opening Curation", "status": "ready"},
            {"id": "matching", "name": "Match Analysis", "status": "ready"},
        ],
    }


@router.get("/job-openings")
def list_job_openings() -> dict[str, Any]:
    return {"job_openings": _list_jobs()}


@router.get("/candidates")
def list_candidates() -> dict[str, Any]:
    return {"candidates": _list_candidates()}


@router.post("/job-openings")
def create_job_opening(request: JobOpeningRequest) -> dict[str, Any]:
    now = _utc_now()
    job_id = f"{_slugify(request.title)}-{uuid4().hex[:8]}"
    skills = [skill.strip() for skill in request.skills_csv.split(",") if skill.strip()]
    payload: dict[str, Any] = {
        "id": job_id,
        "title": request.title,
        "company_name": request.company_name,
        "location": request.location,
        "employment_type": request.employment_type,
        "skills_csv": request.skills_csv,
        "skills": skills,
        "description": request.description,
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "json_path": f"job_openings/{job_id}/job_opening.json",
        "markdown_path": f"job_openings/{job_id}/job_opening.md",
    }
    directory = _job_root() / job_id
    workspace_service.write_json(directory / "job_opening.json", payload)
    workspace_service.write_text(directory / "job_opening.md", _job_markdown(payload))
    return payload


@router.patch("/job-openings/{job_id}/status")
def update_job_opening_status(job_id: str, request: JobOpeningStatusRequest) -> dict[str, Any]:
    payload = _get_job(job_id)
    payload["status"] = request.status
    payload["updated_at"] = _utc_now()
    directory = _job_directory(job_id)
    workspace_service.write_json(directory / "job_opening.json", payload)
    markdown_path = directory / "job_opening.md"
    markdown = markdown_path.read_text(encoding="utf-8") if markdown_path.exists() else _job_markdown(payload)
    workspace_service.write_text(markdown_path, _markdown_with_status(markdown, request.status))
    return payload


@router.post("/job-openings/extract")
def extract_job_opening(
    request: JobOpeningExtractionRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    run_id = f"job-opening-{uuid4()}"
    orchestration_progress_service.create_run(
        run_id=run_id,
        candidate_id="",
        filename=request.source_type,
    )
    orchestration_progress_service.set_status(run_id, status="queued")
    _publish_job_step(run_id, "run_queued", "job_opening_curation", "Job opening curation queued.")
    background_tasks.add_task(_run_job_opening_extraction, run_id, request)
    return {"run_id": run_id}


@router.get("/job-openings/runs/{run_id}")
def get_job_opening_run(run_id: str) -> dict[str, object]:
    payload = orchestration_progress_service.get_run(run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"Unknown job opening run id: {run_id}")
    return payload


@router.get("/job-openings/runs/{run_id}/events")
def stream_job_opening_events(run_id: str) -> StreamingResponse:
    if orchestration_progress_service.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown job opening run id: {run_id}")

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
                message = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
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
