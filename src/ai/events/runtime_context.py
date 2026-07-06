from contextvars import ContextVar


current_run_id: ContextVar[str | None] = ContextVar("current_run_id", default=None)
current_stage: ContextVar[str | None] = ContextVar("current_stage", default=None)
