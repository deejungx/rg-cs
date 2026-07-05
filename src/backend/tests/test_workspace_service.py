from app.services.workspace_service import workspace_service


def test_workspace_file_creation() -> None:
    path = workspace_service.workspace_dir / "runs" / "test-run" / "logs.jsonl"
    workspace_service.write_text(path, '{"ok": true}')
    assert path.exists()
    assert path.read_text(encoding="utf-8") == '{"ok": true}'
