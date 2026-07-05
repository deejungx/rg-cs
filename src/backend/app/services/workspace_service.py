import json
from pathlib import Path

from app.core.config import settings


class WorkspaceService:
    def __init__(self, uploads_dir: Path, workspace_dir: Path) -> None:
        self.uploads_dir = uploads_dir
        self.workspace_dir = workspace_dir

    def ensure_runtime_dirs(self) -> None:
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def write_text(self, path: Path, content: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def write_json(self, path: Path, payload: dict[str, object]) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def read_workspace_path(self, relative_path: str) -> dict[str, object]:
        candidate = (self.workspace_dir / relative_path).resolve()
        if self.workspace_dir.resolve() not in candidate.parents and candidate != self.workspace_dir.resolve():
            raise ValueError("Path escapes workspace root.")
        if not candidate.exists():
            raise FileNotFoundError(f"Workspace file not found: {relative_path}")
        if candidate.is_dir():
            return {
                "path": relative_path,
                "type": "directory",
                "entries": sorted(item.name for item in candidate.iterdir()),
            }
        return {
            "path": relative_path,
            "type": "file",
            "content": candidate.read_text(encoding="utf-8"),
        }


workspace_service = WorkspaceService(settings.uploads_dir, settings.workspace_dir)
