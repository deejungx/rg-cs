"""Reusable runtime guardrails for CrewAI-backed runs."""

from __future__ import annotations

from time import monotonic

from src.shared import CrewAIRunLimits, OpenAITokenPricing


class CrewAIRunLimitExceeded(RuntimeError):
    """Raised when a CrewAI-backed run exceeds its configured budget."""


class CrewAIRunLimiter:
    def __init__(
        self,
        *,
        limits: CrewAIRunLimits | None = None,
        pricing: OpenAITokenPricing | None = None,
    ) -> None:
        self._limits = limits or CrewAIRunLimits()
        self._pricing = pricing
        self._started_at = monotonic()

    @property
    def limits(self) -> CrewAIRunLimits:
        return self._limits

    @property
    def elapsed_seconds(self) -> float:
        return monotonic() - self._started_at

    @property
    def remaining_latency_seconds(self) -> float | None:
        max_latency_seconds = self._limits.max_latency_seconds
        if max_latency_seconds is None:
            return None
        return max(max_latency_seconds - self.elapsed_seconds, 0.0)

    def estimated_cost_usd(self, token_usage: dict[str, int]) -> float:
        if self._pricing is None:
            return 0.0

        prompt_tokens = int(token_usage.get("prompt_tokens", 0) or 0)
        cached_prompt_tokens = int(token_usage.get("cached_prompt_tokens", 0) or 0)
        uncached_prompt_tokens = max(prompt_tokens - cached_prompt_tokens, 0)
        completion_tokens = int(token_usage.get("completion_tokens", 0) or 0)

        return (
            (uncached_prompt_tokens / 1_000_000)
            * self._pricing.input_per_million_usd
            + (cached_prompt_tokens / 1_000_000)
            * self._pricing.cached_input_per_million_usd
            + (completion_tokens / 1_000_000) * self._pricing.output_per_million_usd
        )

    def assert_can_start(self, *, operation: str) -> None:
        max_latency_seconds = self._limits.max_latency_seconds
        if (
            max_latency_seconds is not None
            and self.elapsed_seconds > max_latency_seconds
        ):
            raise CrewAIRunLimitExceeded(
                f"CrewAI run exceeded latency budget before {operation}: "
                f"{self.elapsed_seconds:.2f}s used, {max_latency_seconds:.2f}s allowed."
            )

    def assert_within_limits(
        self, token_usage: dict[str, int], *, operation: str
    ) -> None:
        self.assert_can_start(operation=operation)

        max_cost_usd = self._limits.max_cost_usd
        estimated_cost_usd = self.estimated_cost_usd(token_usage)
        if max_cost_usd is not None and estimated_cost_usd > max_cost_usd:
            raise CrewAIRunLimitExceeded(
                f"CrewAI run exceeded cost budget after {operation}: "
                f"${estimated_cost_usd:.4f} used, ${max_cost_usd:.4f} allowed."
            )
