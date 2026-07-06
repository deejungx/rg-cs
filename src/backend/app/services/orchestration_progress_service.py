import json
from datetime import UTC, datetime
from typing import Any

import redis

from app.core.config import settings


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


class OrchestrationProgressService:
    def __init__(self) -> None:
        self.client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        self.ttl_seconds = settings.orchestration_run_ttl_seconds

    def _run_key(self, run_id: str) -> str:
        return f"orchestration:run:{run_id}"

    def _events_key(self, run_id: str) -> str:
        return f"orchestration:run:{run_id}:events"

    def _sequence_key(self, run_id: str) -> str:
        return f"orchestration:run:{run_id}:seq"

    def _channel(self, run_id: str) -> str:
        return f"orchestration:run:{run_id}:channel"

    def create_run(self, *, run_id: str, candidate_id: str, filename: str) -> None:
        payload = {
            "run_id": run_id,
            "candidate_id": candidate_id,
            "filename": filename,
            "status": "queued",
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
            "result": "",
            "error": "",
        }
        self.client.hset(self._run_key(run_id), mapping=payload)
        self.client.expire(self._run_key(run_id), self.ttl_seconds)
        self.client.expire(self._events_key(run_id), self.ttl_seconds)
        self.client.expire(self._sequence_key(run_id), self.ttl_seconds)

    def set_status(
        self,
        run_id: str,
        *,
        status: str,
        result: dict[str, Any] | None = None,
        error: str = "",
        task_id: str = "",
    ) -> None:
        mapping: dict[str, str] = {
            "status": status,
            "updated_at": _utc_now(),
        }
        if result is not None:
            mapping["result"] = json.dumps(result)
        if error:
            mapping["error"] = error
        if task_id:
            mapping["task_id"] = task_id
        self.client.hset(self._run_key(run_id), mapping=mapping)
        self.client.expire(self._run_key(run_id), self.ttl_seconds)

    def publish_event(self, run_id: str, event: dict[str, Any]) -> dict[str, Any]:
        sequence = self.client.incr(self._sequence_key(run_id))
        payload = {
            "sequence": sequence,
            "timestamp": event.get("timestamp", _utc_now()),
            **event,
        }
        encoded = json.dumps(payload)
        self.client.rpush(self._events_key(run_id), encoded)
        self.client.expire(self._events_key(run_id), self.ttl_seconds)
        self.client.expire(self._sequence_key(run_id), self.ttl_seconds)
        self.client.publish(self._channel(run_id), encoded)
        return payload

    def get_events(self, run_id: str) -> list[dict[str, Any]]:
        raw = self.client.lrange(self._events_key(run_id), 0, -1)
        return [json.loads(item) for item in raw]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        payload = self.client.hgetall(self._run_key(run_id))
        if not payload:
            return None
        result = payload.get("result") or ""
        return {
            "run_id": payload.get("run_id", run_id),
            "candidate_id": payload.get("candidate_id", ""),
            "filename": payload.get("filename", ""),
            "task_id": payload.get("task_id", ""),
            "status": payload.get("status", "unknown"),
            "created_at": payload.get("created_at", ""),
            "updated_at": payload.get("updated_at", ""),
            "error": payload.get("error", ""),
            "result": json.loads(result) if result else None,
        }

    def subscribe(self, run_id: str):
        pubsub = self.client.pubsub()
        pubsub.subscribe(self._channel(run_id))
        return pubsub


orchestration_progress_service = OrchestrationProgressService()
