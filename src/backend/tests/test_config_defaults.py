from app.core.config import Settings


def test_settings_default_local_service_urls() -> None:
    settings = Settings(_env_file=None)

    assert settings.redis_url == "redis://redis:6379/0"
    assert settings.celery_broker_url == "redis://redis:6379/0"
    assert settings.celery_result_backend == "redis://redis:6379/1"
    assert settings.qdrant_url == "http://qdrant:6333"
    assert settings.phoenix_collector_endpoint == "http://phoenix:6006"
    assert settings.pii_redaction_enabled is True
    assert settings.pii_redaction_language == "en"
    assert settings.pii_redaction_entities == "EMAIL_ADDRESS,PHONE_NUMBER,URL"
