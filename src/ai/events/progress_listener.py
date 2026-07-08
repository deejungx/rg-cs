from datetime import UTC, datetime
from typing import Any

from crewai.events.base_event_listener import BaseEventListener
from crewai.events.event_bus import CrewAIEventsBus
from crewai.events.types.crew_events import (
    CrewKickoffCompletedEvent,
    CrewKickoffFailedEvent,
    CrewKickoffStartedEvent,
)
from crewai.events.types.flow_events import (
    FlowFinishedEvent,
    FlowStartedEvent,
    MethodExecutionFailedEvent,
    MethodExecutionFinishedEvent,
    MethodExecutionStartedEvent,
)
from crewai.events.types.llm_guardrail_events import (
    LLMGuardrailCompletedEvent,
    LLMGuardrailStartedEvent,
)
from crewai.events.types.llm_events import (
    LLMCallCompletedEvent,
    LLMCallFailedEvent,
    LLMCallStartedEvent,
)
from crewai.events.types.task_events import (
    TaskCompletedEvent,
    TaskFailedEvent,
    TaskStartedEvent,
)

from app.services.orchestration_progress_service import orchestration_progress_service
from src.ai.events.runtime_context import current_run_id, current_stage
from src.shared import get_openai_token_pricing

_listener_instance: "ProgressListener | None" = None


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _task_label(event: Any) -> str:
    task = getattr(event, "task", None)
    if task is not None:
        return getattr(task, "name", "") or getattr(task, "description", "") or "task"
    return getattr(event, "task_name", None) or "task"


def _estimate_llm_cost_usd(model_name: str | None, usage: dict[str, Any] | None) -> float | None:
    if not model_name or not usage:
        return None
    normalized_model = model_name.split("/")[-1]
    pricing = get_openai_token_pricing(normalized_model)
    if pricing is None:
        return None

    prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
    cached_prompt_tokens = int(usage.get("cached_prompt_tokens", 0) or 0)
    completion_tokens = int(usage.get("completion_tokens", 0) or 0)
    uncached_prompt_tokens = max(0, prompt_tokens - cached_prompt_tokens)

    return round(
        (
            (uncached_prompt_tokens / 1_000_000) * pricing.input_per_million_usd
            + (cached_prompt_tokens / 1_000_000) * pricing.cached_input_per_million_usd
            + (completion_tokens / 1_000_000) * pricing.output_per_million_usd
        ),
        8,
    )


class ProgressListener(BaseEventListener):
    def setup_listeners(self, crewai_event_bus: CrewAIEventsBus) -> None:
        @crewai_event_bus.on(FlowStartedEvent)
        def on_flow_started(source: Any, event: FlowStartedEvent) -> None:
            self._publish("flow_started", event.flow_name, stage=event.flow_name)

        @crewai_event_bus.on(FlowFinishedEvent)
        def on_flow_finished(source: Any, event: FlowFinishedEvent) -> None:
            self._publish("flow_finished", event.flow_name, stage=event.flow_name)

        @crewai_event_bus.on(MethodExecutionStartedEvent)
        def on_method_started(source: Any, event: MethodExecutionStartedEvent) -> None:
            self._publish(
                "step_started",
                event.method_name,
                stage=current_stage.get() or event.flow_name,
                flow_name=event.flow_name,
            )

        @crewai_event_bus.on(MethodExecutionFinishedEvent)
        def on_method_finished(source: Any, event: MethodExecutionFinishedEvent) -> None:
            self._publish(
                "step_completed",
                event.method_name,
                stage=current_stage.get() or event.flow_name,
                flow_name=event.flow_name,
            )

        @crewai_event_bus.on(MethodExecutionFailedEvent)
        def on_method_failed(source: Any, event: MethodExecutionFailedEvent) -> None:
            self._publish(
                "step_failed",
                event.method_name,
                stage=current_stage.get() or event.flow_name,
                flow_name=event.flow_name,
                error=str(event.error),
            )

        @crewai_event_bus.on(CrewKickoffStartedEvent)
        def on_crew_started(source: Any, event: CrewKickoffStartedEvent) -> None:
            self._publish("crew_started", event.crew_name or "crew", stage=current_stage.get())

        @crewai_event_bus.on(CrewKickoffCompletedEvent)
        def on_crew_completed(source: Any, event: CrewKickoffCompletedEvent) -> None:
            self._publish("crew_completed", event.crew_name or "crew", stage=current_stage.get())

        @crewai_event_bus.on(CrewKickoffFailedEvent)
        def on_crew_failed(source: Any, event: CrewKickoffFailedEvent) -> None:
            self._publish(
                "crew_failed",
                event.crew_name or "crew",
                stage=current_stage.get(),
                error=event.error,
            )

        @crewai_event_bus.on(TaskStartedEvent)
        def on_task_started(source: Any, event: TaskStartedEvent) -> None:
            self._publish("task_started", _task_label(event), stage=current_stage.get())

        @crewai_event_bus.on(TaskCompletedEvent)
        def on_task_completed(source: Any, event: TaskCompletedEvent) -> None:
            self._publish("task_completed", _task_label(event), stage=current_stage.get())

        @crewai_event_bus.on(TaskFailedEvent)
        def on_task_failed(source: Any, event: TaskFailedEvent) -> None:
            self._publish(
                "task_failed",
                _task_label(event),
                stage=current_stage.get(),
                error=event.error,
            )

        @crewai_event_bus.on(LLMGuardrailStartedEvent)
        def on_guardrail_started(source: Any, event: LLMGuardrailStartedEvent) -> None:
            self._publish(
                "guardrail_started",
                event.guardrail_name or "guardrail",
                stage=current_stage.get(),
                task_name=event.task_name,
                retry_count=event.retry_count,
                guardrail_type=event.guardrail_type,
            )

        @crewai_event_bus.on(LLMGuardrailCompletedEvent)
        def on_guardrail_completed(source: Any, event: LLMGuardrailCompletedEvent) -> None:
            self._publish(
                "guardrail_completed",
                event.guardrail_name or "guardrail",
                stage=current_stage.get(),
                task_name=event.task_name,
                retry_count=event.retry_count,
                guardrail_type=event.guardrail_type,
                success=event.success,
                result=str(event.result) if event.result is not None else "",
                error=event.error or "",
            )

        @crewai_event_bus.on(LLMCallStartedEvent)
        def on_llm_call_started(source: Any, event: LLMCallStartedEvent) -> None:
            self._publish(
                "llm_call_started",
                event.model or "llm_call",
                stage=current_stage.get(),
                task_name=getattr(event, "task_name", None),
                agent_role=getattr(event, "agent_role", None),
                model=event.model,
                call_id=event.call_id,
            )

        @crewai_event_bus.on(LLMCallCompletedEvent)
        def on_llm_call_completed(source: Any, event: LLMCallCompletedEvent) -> None:
            usage = event.usage or {}
            self._publish(
                "llm_call_completed",
                event.model or "llm_call",
                stage=current_stage.get(),
                task_name=getattr(event, "task_name", None),
                agent_role=getattr(event, "agent_role", None),
                model=event.model,
                call_id=event.call_id,
                finish_reason=event.finish_reason,
                usage=usage,
                estimated_cost_usd=_estimate_llm_cost_usd(event.model, usage),
            )

        @crewai_event_bus.on(LLMCallFailedEvent)
        def on_llm_call_failed(source: Any, event: LLMCallFailedEvent) -> None:
            self._publish(
                "llm_call_failed",
                event.model or "llm_call",
                stage=current_stage.get(),
                task_name=getattr(event, "task_name", None),
                agent_role=getattr(event, "agent_role", None),
                model=event.model,
                call_id=event.call_id,
                error=event.error,
            )

    def _publish(self, event_type: str, label: str, **extra: Any) -> None:
        run_id = current_run_id.get()
        if not run_id:
            return
        try:
            orchestration_progress_service.publish_event(
                run_id,
                {
                    "run_id": run_id,
                    "type": event_type,
                    "label": label,
                    "stage": extra.pop("stage", current_stage.get() or ""),
                    "timestamp": _utc_now(),
                    **extra,
                },
            )
        except Exception:
            return


def ensure_progress_listener() -> None:
    global _listener_instance
    if _listener_instance is None:
        _listener_instance = ProgressListener()
