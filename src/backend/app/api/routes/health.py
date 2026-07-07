import httpx
from fastapi import APIRouter

from app.api.deps import task_queue
from app.core.config import settings
from app.services.orchestration_progress_service import orchestration_progress_service

router = APIRouter(tags=["health"])


def _redis_health() -> bool:
    try:
        return bool(orchestration_progress_service.client.ping())
    except Exception:
        return False


def _http_health(url: str) -> bool:
    try:
        response = httpx.get(url, timeout=1.0)
        return response.status_code < 500
    except Exception:
        return False


def _workspace_health() -> bool:
    try:
        settings.workspace_dir.mkdir(parents=True, exist_ok=True)
        probe = settings.workspace_dir / ".healthcheck"
        probe.write_text("ok", encoding="utf-8")
        return probe.read_text(encoding="utf-8") == "ok"
    except Exception:
        return False


@router.get("/health")
def health() -> dict[str, object]:
    services = {
        "redis": _redis_health(),
        "worker": task_queue.health(),
        "phoenix": _http_health(settings.phoenix_collector_endpoint),
        "qdrant": _http_health(settings.qdrant_url),
        "workspace": _workspace_health(),
    }
    return {
        "status": "ok" if any(services.values()) else "degraded",
        "broker": services["worker"],
        "services": services,
    }
