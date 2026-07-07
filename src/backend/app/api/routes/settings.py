from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.config import settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


class ContainmentSettings(BaseModel):
    max_cost_usd: float | None = Field(default=None, ge=0)
    max_latency_seconds: float | None = Field(default=None, ge=0)


@router.get("/containment")
def get_containment_settings() -> ContainmentSettings:
    return ContainmentSettings(
        max_cost_usd=settings.crewai_run_max_cost_usd,
        max_latency_seconds=settings.crewai_run_max_latency_seconds,
    )


@router.put("/containment")
def update_containment_settings(request: ContainmentSettings) -> ContainmentSettings:
    settings.crewai_run_max_cost_usd = request.max_cost_usd
    settings.crewai_run_max_latency_seconds = request.max_latency_seconds
    return get_containment_settings()
