import pytest

from src.ai.runtime.crewai_run_limiter import (
    CrewAIRunLimitExceeded,
    CrewAIRunLimiter,
)
from src.shared import CrewAIRunLimits, OpenAITokenPricing


def test_crewai_run_limiter_estimates_cost_with_cached_tokens() -> None:
    limiter = CrewAIRunLimiter(
        limits=CrewAIRunLimits(max_cost_usd=1.0, max_latency_seconds=60.0),
        pricing=OpenAITokenPricing(
            input_per_million_usd=1.0,
            cached_input_per_million_usd=0.5,
            output_per_million_usd=2.0,
        ),
    )

    estimated_cost = limiter.estimated_cost_usd(
        {
            "prompt_tokens": 1_000_000,
            "cached_prompt_tokens": 200_000,
            "completion_tokens": 100_000,
        }
    )

    assert estimated_cost == pytest.approx(1.1)


def test_crewai_run_limiter_raises_when_cost_budget_is_exceeded() -> None:
    limiter = CrewAIRunLimiter(
        limits=CrewAIRunLimits(max_cost_usd=0.05, max_latency_seconds=60.0),
        pricing=OpenAITokenPricing(
            input_per_million_usd=1.0,
            cached_input_per_million_usd=0.5,
            output_per_million_usd=2.0,
        ),
    )

    with pytest.raises(CrewAIRunLimitExceeded, match="cost budget"):
        limiter.assert_within_limits(
            {
                "prompt_tokens": 40_000,
                "cached_prompt_tokens": 0,
                "completion_tokens": 10_000,
            },
            operation="test kickoff",
        )


def test_crewai_run_limiter_raises_when_latency_budget_is_exceeded() -> None:
    limiter = CrewAIRunLimiter(
        limits=CrewAIRunLimits(max_cost_usd=1.0, max_latency_seconds=0.0),
        pricing=None,
    )

    with pytest.raises(CrewAIRunLimitExceeded, match="latency budget"):
        limiter.assert_can_start(operation="test kickoff")
