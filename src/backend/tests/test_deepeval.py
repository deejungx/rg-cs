import sys
from types import ModuleType

from src.ai.integrations import deepeval_crewai


def test_deepeval_instrumentation_runs_once(monkeypatch) -> None:
    calls = {"count": 0}

    def instrument_crewai() -> None:
        calls["count"] += 1

    integration_module = ModuleType("deepeval.integrations.crewai")
    integration_module.instrument_crewai = instrument_crewai

    monkeypatch.setitem(sys.modules, "deepeval.integrations.crewai", integration_module)
    monkeypatch.setattr(deepeval_crewai, "instrument_crewai", instrument_crewai)
    monkeypatch.setattr(deepeval_crewai, "_initialization_attempted", False)
    monkeypatch.setattr(deepeval_crewai, "_instrumented", False)

    assert deepeval_crewai.initialize_deepeval() is True
    assert deepeval_crewai.initialize_deepeval() is True
    assert calls["count"] == 1


def test_deepeval_instrumentation_respects_disable_flag(monkeypatch) -> None:
    monkeypatch.setattr(deepeval_crewai, "_initialization_attempted", False)
    monkeypatch.setattr(deepeval_crewai, "_instrumented", False)
    monkeypatch.setattr(deepeval_crewai.settings, "deepeval_enabled", False)

    assert deepeval_crewai.initialize_deepeval() is False

    monkeypatch.setattr(deepeval_crewai.settings, "deepeval_enabled", True)


def test_deepeval_falls_back_to_native_crewai_when_unavailable() -> None:
    assert deepeval_crewai.Agent is not None
    assert deepeval_crewai.Crew is not None
    assert deepeval_crewai.LLM is not None
    assert deepeval_crewai.tool is not None
