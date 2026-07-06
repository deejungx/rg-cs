import sys
from types import ModuleType, SimpleNamespace

import pytest
from opentelemetry.sdk.trace import TracerProvider

from src.ai.crews.cv_extraction_crew import CvExtractionCrew, _TOKEN_USAGE_FIELDS
from src.ai.tracing import phoenix


def test_trace_endpoint_is_normalized() -> None:
    assert phoenix._trace_endpoint("http://phoenix:6006") == (
        "http://phoenix:6006/v1/traces"
    )
    assert phoenix._trace_endpoint("http://phoenix:6006/v1/traces") == (
        "http://phoenix:6006/v1/traces"
    )


def test_phoenix_uses_event_and_openai_instrumentation(monkeypatch) -> None:
    calls: dict[str, dict[str, object]] = {}
    provider = TracerProvider()

    def register(**kwargs):
        calls["register"] = kwargs
        return provider

    class CrewAIInstrumentor:
        def instrument(self, **kwargs) -> None:
            calls["crewai"] = kwargs

    class OpenAIInstrumentor:
        def instrument(self, **kwargs) -> None:
            calls["openai"] = kwargs

    crewai_module = ModuleType("openinference.instrumentation.crewai")
    crewai_module.CrewAIInstrumentor = CrewAIInstrumentor
    openai_module = ModuleType("openinference.instrumentation.openai")
    openai_module.OpenAIInstrumentor = OpenAIInstrumentor
    phoenix_otel_module = ModuleType("phoenix.otel")
    phoenix_otel_module.register = register

    monkeypatch.setitem(
        sys.modules,
        "openinference.instrumentation.crewai",
        crewai_module,
    )
    monkeypatch.setitem(
        sys.modules,
        "openinference.instrumentation.openai",
        openai_module,
    )
    monkeypatch.setitem(sys.modules, "phoenix.otel", phoenix_otel_module)
    monkeypatch.setattr(phoenix, "_initialization_attempted", False)
    monkeypatch.setattr(phoenix, "_tracer_provider", None)

    assert phoenix.initialize_phoenix() is provider
    assert calls["register"] == {
        "project_name": "default",
        "endpoint": phoenix._trace_endpoint(phoenix.settings.phoenix_collector_endpoint),
        "batch": True,
        "set_global_tracer_provider": False,
        "verbose": False,
        "auto_instrument": False,
    }
    assert calls["crewai"] == {
        "skip_dep_check": True,
        "tracer_provider": provider,
        "use_event_listener": True,
        "create_llm_spans": False,
    }
    assert calls["openai"] == {"tracer_provider": provider}


def test_traced_operation_preserves_application_errors(monkeypatch) -> None:
    monkeypatch.setattr(phoenix, "_initialization_attempted", True)
    monkeypatch.setattr(phoenix, "_tracer_provider", None)

    with pytest.raises(LookupError, match="operation failed"):
        with phoenix.traced_operation("failing-operation"):
            raise LookupError("operation failed")


def test_crew_token_usage_is_aggregated() -> None:
    crew = object.__new__(CvExtractionCrew)
    crew._token_usage = {field: 0 for field in _TOKEN_USAGE_FIELDS}

    first = SimpleNamespace(
        token_usage=SimpleNamespace(
            model_dump=lambda: {
                "prompt_tokens": 100,
                "completion_tokens": 25,
                "total_tokens": 125,
                "successful_requests": 1,
            }
        )
    )
    second = SimpleNamespace(
        token_usage=SimpleNamespace(
            model_dump=lambda: {
                "prompt_tokens": 50,
                "completion_tokens": 10,
                "total_tokens": 60,
                "successful_requests": 1,
            }
        )
    )

    crew._record_token_usage(first)
    crew._record_token_usage(second)

    assert crew.token_usage["prompt_tokens"] == 150
    assert crew.token_usage["completion_tokens"] == 35
    assert crew.token_usage["total_tokens"] == 185
    assert crew.token_usage["successful_requests"] == 2
