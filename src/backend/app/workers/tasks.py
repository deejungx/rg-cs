from app.services.orchestration_progress_service import orchestration_progress_service
from src.ai.pipelines.cv_extraction_flow import run_cv_extraction_flow
from src.ai.pipelines.candidate_analysis_flow import run_candidate_analysis

from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.extract_cv")
def extract_cv(candidate_id: str, source_path: str, filename: str, content_type: str) -> dict[str, object]:
    return run_cv_extraction_flow(
        candidate_id=candidate_id,
        source_path=source_path,
        filename=filename,
        content_type=content_type,
    )


@celery_app.task(name="app.workers.tasks.run_candidate_analysis")
def run_candidate_analysis_task(
    run_id: str,
    candidate_id: str,
    source_path: str,
    filename: str,
    content_type: str,
    job_title: str,
    job_description: str,
    company_name: str,
    location: str,
    skills_csv: str,
) -> dict[str, object]:
    orchestration_progress_service.set_status(
        run_id,
        status="running",
    )
    orchestration_progress_service.publish_event(
        run_id,
        {
            "run_id": run_id,
            "type": "worker_started",
            "label": "candidate_analysis_worker",
            "stage": "candidate_analysis",
            "message": "Worker picked up the orchestration run.",
        },
    )
    try:
        result = run_candidate_analysis(
            analysis_id=run_id,
            candidate_id=candidate_id,
            source_path=source_path,
            filename=filename,
            content_type=content_type,
            job_title=job_title,
            job_description=job_description,
            company_name=company_name,
            location=location,
            skills_csv=skills_csv,
        )
        payload = result.model_dump(mode="json")
        orchestration_progress_service.set_status(
            run_id,
            status="completed",
            result=payload,
        )
        orchestration_progress_service.publish_event(
            run_id,
            {
                "run_id": run_id,
                "type": "run_completed",
                "label": "candidate_analysis",
                "stage": "candidate_analysis",
                "message": "Orchestration finished successfully.",
            },
        )
        return payload
    except Exception as exc:
        orchestration_progress_service.set_status(
            run_id,
            status="failed",
            error=str(exc),
        )
        orchestration_progress_service.publish_event(
            run_id,
            {
                "run_id": run_id,
                "type": "run_failed",
                "label": "candidate_analysis",
                "stage": "candidate_analysis",
                "error": str(exc),
                "message": "Orchestration failed.",
            },
        )
        raise
