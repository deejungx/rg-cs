from app.core.config import settings


def test_containment_settings_can_be_updated(client) -> None:
    original_cost = settings.crewai_run_max_cost_usd
    original_latency = settings.crewai_run_max_latency_seconds
    try:
        response = client.put(
            "/api/settings/containment",
            json={"max_cost_usd": 0.123, "max_latency_seconds": 45},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload == {"max_cost_usd": 0.123, "max_latency_seconds": 45.0}
        assert settings.crewai_run_max_cost_usd == 0.123
        assert settings.crewai_run_max_latency_seconds == 45

        get_response = client.get("/api/settings/containment")
        assert get_response.status_code == 200
        assert get_response.json() == payload
    finally:
        settings.crewai_run_max_cost_usd = original_cost
        settings.crewai_run_max_latency_seconds = original_latency
