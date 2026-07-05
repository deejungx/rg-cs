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
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"
    qdrant_url: str = "http://qdrant:6333"
    phoenix_collector_endpoint: str = "http://phoenix:6006"
    phoenix_project_name: str = "default"
    uploads_dir: Path = Path("/app/uploads")
    workspace_dir: Path = Path("/app/workspace")
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
