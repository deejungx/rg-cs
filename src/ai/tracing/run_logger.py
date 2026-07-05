import json

from app.services.workspace_service import workspace_service


def append_log(run_id: str, event: dict[str, object]) -> None:
    log_path = workspace_service.workspace_dir / "runs" / run_id / "logs.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")
