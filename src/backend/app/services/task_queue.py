from celery import Celery

from app.core.config import settings


class TaskQueueService:
    def __init__(self, app: Celery) -> None:
        self.app = app

    def enqueue_cv_extraction(
        self,
        *,
        candidate_id: str,
        source_path: str,
        filename: str,
        content_type: str,
    ):
        return self.app.send_task(
            "app.workers.tasks.extract_cv",
            kwargs={
                "candidate_id": candidate_id,
                "source_path": source_path,
                "filename": filename,
                "content_type": content_type,
            },
        )

    def enqueue_candidate_analysis(
        self,
        *,
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
    ):
        return self.app.send_task(
            "app.workers.tasks.run_candidate_analysis",
            kwargs={
                "run_id": run_id,
                "candidate_id": candidate_id,
                "source_path": source_path,
                "filename": filename,
                "content_type": content_type,
                "job_title": job_title,
                "job_description": job_description,
                "company_name": company_name,
                "location": location,
                "skills_csv": skills_csv,
            },
        )

    def health(self) -> bool:
        try:
            with self.app.connection_or_acquire() as connection:
                connection.ensure_connection(max_retries=1)
            return True
        except Exception:
            return False


task_queue = TaskQueueService(
    Celery(
        "ai_match_client",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
    )
)
