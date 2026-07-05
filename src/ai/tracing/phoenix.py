"""Phoenix/OpenInference tracing setup for CrewAI and custom application spans."""

import logging
from contextlib import contextmanager
from threading import Lock
from typing import Iterator

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from app.core.config import settings

logger = logging.getLogger(__name__)

_TRACER_NAME = "recruitment-ai"
_initialization_lock = Lock()
_initialization_attempted = False
_tracer_provider: TracerProvider | None = None


def _trace_endpoint(collector_endpoint: str) -> str:
    """Return the OTLP HTTP traces endpoint expected by Phoenix."""

    endpoint = collector_endpoint.rstrip("/")
    if endpoint.endswith("/v1/traces"):
        return endpoint
    return f"{endpoint}/v1/traces"


def initialize_phoenix() -> TracerProvider | None:
    """Register Phoenix and instrument CrewAI once per application process.

    Tracing is optional infrastructure. A missing dependency or unavailable setup
    must not prevent CV processing from running.
    """

    global _initialization_attempted, _tracer_provider

    if _initialization_attempted:
        return _tracer_provider

    with _initialization_lock:
        if _initialization_attempted:
            return _tracer_provider

        _initialization_attempted = True
        try:
            from openinference.instrumentation.crewai import CrewAIInstrumentor
            from openinference.instrumentation.openai import OpenAIInstrumentor
            from phoenix.otel import register

            provider = register(
                project_name=settings.phoenix_project_name,
                endpoint=_trace_endpoint(settings.phoenix_collector_endpoint),
                batch=True,
                set_global_tracer_provider=False,
                verbose=False,
                auto_instrument=False,
            )
            CrewAIInstrumentor().instrument(
                skip_dep_check=True,
                tracer_provider=provider,
                use_event_listener=True,
                create_llm_spans=False,
            )
            OpenAIInstrumentor().instrument(tracer_provider=provider)
            _tracer_provider = provider
            logger.info(
                "Phoenix tracing initialized for project %s at %s",
                settings.phoenix_project_name,
                _trace_endpoint(settings.phoenix_collector_endpoint),
            )
        except Exception:
            logger.warning(
                "Phoenix tracing could not be initialized; continuing without exported traces.",
                exc_info=True,
            )

    return _tracer_provider


def flush_phoenix(timeout_millis: int = 5000) -> bool:
    """Flush queued spans when a process is about to finish."""

    if _tracer_provider is None:
        return True
    try:
        return bool(_tracer_provider.force_flush(timeout_millis=timeout_millis))
    except Exception:
        logger.warning("Phoenix spans could not be flushed.", exc_info=True)
        return False


@contextmanager
def traced_operation(
    name: str,
    attributes: dict[str, object] | None = None,
) -> Iterator[None]:
    """Create a custom span without swallowing exceptions from the operation."""

    provider = initialize_phoenix()
    tracer = (
        provider.get_tracer(_TRACER_NAME)
        if provider is not None
        else trace.get_tracer(_TRACER_NAME)
    )
    with tracer.start_as_current_span(name) as span:
        for key, value in (attributes or {}).items():
            span.set_attribute(key, str(value))
        yield
