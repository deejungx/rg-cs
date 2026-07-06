import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
test_home = Path("/tmp/rg-cs-test-home")
test_home.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HOME", str(test_home))
os.environ.setdefault("XDG_DATA_HOME", str(test_home / ".local" / "share"))

from app.core.config import settings
from app.main import app
from app.services.upload_service import upload_service
from app.services.workspace_service import workspace_service


@pytest.fixture(autouse=True)
def isolate_runtime_dirs(tmp_path: Path) -> None:
    settings.uploads_dir = tmp_path / "uploads"
    settings.workspace_dir = tmp_path / "workspace"
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.workspace_dir.mkdir(parents=True, exist_ok=True)
    upload_service.uploads_dir = settings.uploads_dir
    workspace_service.uploads_dir = settings.uploads_dir
    workspace_service.workspace_dir = settings.workspace_dir


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
