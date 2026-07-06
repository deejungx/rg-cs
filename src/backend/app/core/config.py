from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_env: str = "development"
    backend_port: int = 8000
    frontend_port: int = 8080
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    qdrant_url: str = "http://localhost:6333"
    phoenix_collector_endpoint: str = "http://localhost:6006"
    phoenix_project_name: str = "default"
    uploads_dir: Path = Path("/app/uploads")
    workspace_dir: Path = Path("/app/workspace")
    default_temperature: float = 0.1
    model_provider: str = "auto"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    deepeval_enabled: bool = True
    pii_redaction_enabled: bool = True
    pii_redaction_language: str = "en"
    pii_redaction_entities: str = "EMAIL_ADDRESS,PHONE_NUMBER,URL"
    crewai_run_max_cost_usd: float | None = 0.05
    crewai_run_max_latency_seconds: float | None = 180.0
    openai_input_token_cost_per_million_usd: float | None = None
    openai_cached_input_token_cost_per_million_usd: float | None = None
    openai_output_token_cost_per_million_usd: float | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
