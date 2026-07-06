from dataclasses import dataclass

from app.core.config import settings


@dataclass(frozen=True)
class ModelProvider:
    name: str
    mode: str
    uses_live_llm: bool
    reason: str


def get_model_provider() -> ModelProvider:
    configured = settings.model_provider.strip().lower()
    has_openai_key = bool(settings.openai_api_key.strip())

    if configured == "mock":
        return ModelProvider(
            name="mock",
            mode="mock",
            uses_live_llm=False,
            reason="MODEL_PROVIDER is set to mock.",
        )

    if configured in {"openai", "auto"} and has_openai_key:
        return ModelProvider(
            name="openai",
            mode="live",
            uses_live_llm=True,
            reason="OpenAI is enabled because an API key is configured.",
        )

    if configured == "openai" and not has_openai_key:
        return ModelProvider(
            name="mock",
            mode="mock",
            uses_live_llm=False,
            reason="MODEL_PROVIDER requested OpenAI, but OPENAI_API_KEY is empty.",
        )

    return ModelProvider(
        name="mock",
        mode="mock",
        uses_live_llm=False,
        reason="No API key is configured, so deterministic mock mode is active.",
    )
