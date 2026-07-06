import json

from app.services.workspace_service import workspace_service


def _normalize_log_event(event: dict[str, object]) -> dict[str, object]:
    normalized = dict(event)
    token_usage = normalized.get("token_usage")
    if isinstance(token_usage, dict):
        total_tokens = token_usage.get("total_tokens")
        if isinstance(total_tokens, int):
            normalized.setdefault("total_tokens_consumed", total_tokens)

    estimated_cost_usd = normalized.get("estimated_cost_usd")
    if isinstance(estimated_cost_usd, int | float):
        normalized.setdefault("total_cost_usd", float(estimated_cost_usd))

    return normalized


def append_log(run_id: str, event: dict[str, object]) -> None:
    log_path = workspace_service.workspace_dir / "runs" / run_id / "logs.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_normalize_log_event(event)) + "\n")
