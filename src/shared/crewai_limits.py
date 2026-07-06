"""Shared CrewAI run-budget defaults and pricing helpers."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.core.config import settings

DEFAULT_CREWAI_RUN_MAX_COST_USD = settings.crewai_run_max_cost_usd
DEFAULT_CREWAI_RUN_MAX_LATENCY_SECONDS = settings.crewai_run_max_latency_seconds


class OpenAITokenPricing(BaseModel):
    """Per-1M-token pricing used for run-cost estimation."""

    model_config = ConfigDict(frozen=True)

    input_per_million_usd: float
    cached_input_per_million_usd: float = 0.0
    output_per_million_usd: float


class CrewAIRunLimits(BaseModel):
    """Reusable cost and latency limits for a single CrewAI-backed run."""

    model_config = ConfigDict(frozen=True)

    max_cost_usd: float | None = DEFAULT_CREWAI_RUN_MAX_COST_USD
    max_latency_seconds: float | None = DEFAULT_CREWAI_RUN_MAX_LATENCY_SECONDS


DEFAULT_OPENAI_TOKEN_PRICING_BY_MODEL: dict[str, OpenAITokenPricing] = {
    # Override these via config when you need different pricing for a deployment.
    "gpt-4o-mini": OpenAITokenPricing(
        input_per_million_usd=0.15,
        cached_input_per_million_usd=0.08,
        output_per_million_usd=0.60,
    ),
    "gpt-5.4-mini": OpenAITokenPricing(
        input_per_million_usd=0.75,
        cached_input_per_million_usd=0.08,
        output_per_million_usd=4.50,
    ),
}


def get_openai_token_pricing(model_name: str) -> OpenAITokenPricing | None:
    """Return the shared default pricing estimate for a model, if known."""

    return DEFAULT_OPENAI_TOKEN_PRICING_BY_MODEL.get(model_name)
