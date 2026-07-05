from app.workers.celery_app import celery_app


def test_celery_task_registered() -> None:
    assert "app.workers.tasks.extract_cv" in celery_app.tasks
