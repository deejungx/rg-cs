from contextlib import nullcontext

from app.core.config import settings
from src.ai.pipelines import cv_extraction_flow


def test_run_cv_extraction_flow_uses_settings_limits(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeFlow:
        def __init__(self, **kwargs) -> None:
            captured["init_kwargs"] = kwargs

        def kickoff(self) -> dict[str, object]:
            captured["kickoff_called"] = True
            return {"ok": True}

    monkeypatch.setattr(cv_extraction_flow, "CvExtractionFlow", FakeFlow)
    monkeypatch.setattr(cv_extraction_flow, "traced_operation", lambda *args, **kwargs: nullcontext())
    monkeypatch.setattr(cv_extraction_flow, "flush_phoenix", lambda: True)

    settings.crewai_run_max_cost_usd = 0.42
    settings.crewai_run_max_latency_seconds = 123.0

    result = cv_extraction_flow.run_cv_extraction_flow(
        candidate_id="candidate-1",
        source_path="/tmp/resume.pdf",
        filename="resume.pdf",
        content_type="application/pdf",
    )

    run_limits = captured["init_kwargs"]["run_limits"]
    assert result == {"ok": True}
    assert captured["kickoff_called"] is True
    assert run_limits.max_cost_usd == 0.42
    assert run_limits.max_latency_seconds == 123.0


def test_run_cv_extraction_flow_allows_limit_overrides(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeFlow:
        def __init__(self, **kwargs) -> None:
            captured["init_kwargs"] = kwargs

        def kickoff(self) -> dict[str, object]:
            return {"ok": True}

    monkeypatch.setattr(cv_extraction_flow, "CvExtractionFlow", FakeFlow)
    monkeypatch.setattr(cv_extraction_flow, "traced_operation", lambda *args, **kwargs: nullcontext())
    monkeypatch.setattr(cv_extraction_flow, "flush_phoenix", lambda: True)

    settings.crewai_run_max_cost_usd = 0.42
    settings.crewai_run_max_latency_seconds = 123.0

    cv_extraction_flow.run_cv_extraction_flow(
        candidate_id="candidate-1",
        source_path="/tmp/resume.pdf",
        filename="resume.pdf",
        content_type="application/pdf",
        max_cost_usd=0.11,
        max_latency_seconds=45.0,
    )

    run_limits = captured["init_kwargs"]["run_limits"]
    assert run_limits.max_cost_usd == 0.11
    assert run_limits.max_latency_seconds == 45.0
