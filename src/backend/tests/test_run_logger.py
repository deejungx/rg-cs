import json

from src.ai.tracing.run_logger import append_log


def test_append_log_persists_total_tokens_and_cost(tmp_path) -> None:
    from app.core.config import settings
    from app.services.workspace_service import workspace_service

    settings.workspace_dir = tmp_path / "workspace"
    workspace_service.workspace_dir = settings.workspace_dir

    append_log(
        "run-123",
        {
            "stage": "cv_extraction",
            "token_usage": {"total_tokens": 321, "prompt_tokens": 200},
            "estimated_cost_usd": 0.0123,
        },
    )

    log_path = settings.workspace_dir / "runs" / "run-123" / "logs.jsonl"
    event = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])

    assert event["total_tokens_consumed"] == 321
    assert event["total_cost_usd"] == 0.0123


def test_append_log_preserves_explicit_totals(tmp_path) -> None:
    from app.core.config import settings
    from app.services.workspace_service import workspace_service

    settings.workspace_dir = tmp_path / "workspace"
    workspace_service.workspace_dir = settings.workspace_dir

    append_log(
        "run-123",
        {
            "stage": "cv_extraction",
            "token_usage": {"total_tokens": 321},
            "estimated_cost_usd": 0.0123,
            "total_tokens_consumed": 999,
            "total_cost_usd": 9.99,
        },
    )

    log_path = settings.workspace_dir / "runs" / "run-123" / "logs.jsonl"
    event = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])

    assert event["total_tokens_consumed"] == 999
    assert event["total_cost_usd"] == 9.99
