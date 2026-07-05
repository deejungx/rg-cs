from src.ai.pipelines.cv_extraction_flow import run_cv_extraction_flow

from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.extract_cv")
def extract_cv(candidate_id: str, source_path: str, filename: str, content_type: str) -> dict[str, object]:
    return run_cv_extraction_flow(
        candidate_id=candidate_id,
        source_path=source_path,
        filename=filename,
        content_type=content_type,
    )
