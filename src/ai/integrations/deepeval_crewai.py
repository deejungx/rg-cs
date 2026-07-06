"""CrewAI plus DeepEval adapter.

This module keeps DeepEval-specific imports out of domain code while exposing
the CrewAI shims needed for tracing and evaluation.
"""

import logging
from threading import Lock

from crewai import Agent as NativeAgent
from crewai import Crew as NativeCrew
from crewai import LLM as NativeLLM
from crewai.tools.base_tool import tool as native_tool

from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    from deepeval.integrations.crewai import Agent, Crew, LLM, tool
    from deepeval.integrations.crewai import instrument_crewai

    DEEPEVAL_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised before deps are synced.
    Agent = NativeAgent
    Crew = NativeCrew
    LLM = NativeLLM
    tool = native_tool
    instrument_crewai = None
    DEEPEVAL_AVAILABLE = False

_initialization_lock = Lock()
_initialization_attempted = False
_instrumented = False


def initialize_deepeval() -> bool:
    """Register DeepEval's CrewAI listener once per process."""

    global _initialization_attempted, _instrumented

    if _initialization_attempted:
        return _instrumented

    with _initialization_lock:
        if _initialization_attempted:
            return _instrumented

        _initialization_attempted = True
        if not settings.deepeval_enabled:
            logger.info("DeepEval instrumentation disabled by configuration.")
            return False
        if instrument_crewai is None:
            logger.info("DeepEval is not installed; skipping CrewAI instrumentation.")
            return False

        try:
            instrument_crewai()
            _instrumented = True
            logger.info("DeepEval CrewAI instrumentation initialized.")
        except Exception:
            logger.warning(
                "DeepEval instrumentation could not be initialized; continuing without DeepEval traces.",
                exc_info=True,
            )

    return _instrumented
