"""IncidentSherpa webhook API — POST /trigger, GET /events (SSE), GET /health.

Phase 1 behavior is honest about its blockers: with CLICKHOUSE_* env vars
empty (BUILD-STATE.md B2), /trigger returns 503 instead of pretending to
persist, and /health reports every unconfigured dependency as "blocked".
No mocks, no fake "ok".
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from apps.worker.agent import TypedEvent
from libs.clickhouse import record_event
from libs.errors import NotConfiguredError

app = FastAPI(title="IncidentSherpa webhook API", version="0.1.0")


# --------------------------------------------------------------------------
# Alert payload (pydantic-validated)
# --------------------------------------------------------------------------


class AlertPayload(BaseModel):
    """Inbound monitoring alert. Bad shapes are rejected with 422."""

    service: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    value: float
    timestamp: datetime
    incident_id: str | None = None


# --------------------------------------------------------------------------
# In-process event bus — the worker/agent publishes here; /events streams it.
# --------------------------------------------------------------------------


class EventBus:
    """Fan-out hub: each SSE subscriber gets its own asyncio.Queue."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(queue)

    def publish(self, item: dict[str, Any]) -> None:
        for queue in list(self._subscribers):
            queue.put_nowait(item)


bus = EventBus()

# Idempotency: keys of every alert already accepted by this process.
# Registered at RECEIPT (before persistence) so the same alert is never
# double-processed, even when the first attempt 503'd on an open blocker.
# Durable (ClickHouse-backed) dedupe replaces this in Phase 2.
_seen_keys: set[str] = set()


def _payload_hash(alert: AlertPayload) -> str:
    """Deterministic hash of the validated payload (field order is fixed)."""
    return hashlib.sha256(alert.model_dump_json().encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# POST /trigger — alert ingest
# --------------------------------------------------------------------------


@app.post("/trigger")
async def trigger(
    alert: AlertPayload,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> dict[str, Any]:
    key = idempotency_key or _payload_hash(alert)
    if key in _seen_keys:
        return {"duplicate": True}
    _seen_keys.add(key)

    incident_id = alert.incident_id or f"inc-{key[:12]}"
    event = TypedEvent(
        ts=datetime.now(UTC),
        incident_id=incident_id,
        event_type="alert.received",
        payload=alert.model_dump(mode="json"),
    )
    try:
        record_event(event.ts, event.incident_id, event.event_type, event.payload)
    except NotConfiguredError as exc:
        # Honest unconfigured state — the alert was NOT persisted.
        raise HTTPException(
            status_code=503,
            detail=f"ClickHouse not configured — see BUILD-STATE.md blockers ({exc})",
        ) from exc

    bus.publish(
        {
            "ts": event.ts.isoformat(),
            "incident_id": event.incident_id,
            "event_type": event.event_type,
            "payload": event.payload,
        }
    )
    return {"duplicate": False, "incident_id": incident_id, "event_type": event.event_type}


# --------------------------------------------------------------------------
# GET /events — SSE stream of typed events
# --------------------------------------------------------------------------


@app.get("/events")
async def events(request: Request) -> StreamingResponse:
    queue = bus.subscribe()

    async def stream() -> Any:
        try:
            yield ": connected\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=15.0)
                except TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                yield f"data: {json.dumps(item)}\n\n"
        finally:
            bus.unsubscribe(queue)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable proxy buffering (nginx/Render)
            "Connection": "keep-alive",
        },
    )


# --------------------------------------------------------------------------
# GET /health — per-dependency configured/blocked from real env presence
# --------------------------------------------------------------------------

# Dependency -> env vars whose presence means "configured". This is a real
# configuration check, NOT a liveness claim — actual live probes deepen in
# later phases. We never report "ok" for something we haven't checked.
DEPENDENCY_ENV_VARS: dict[str, tuple[str, ...]] = {
    "clickhouse": ("CLICKHOUSE_HOST", "CLICKHOUSE_USER", "CLICKHOUSE_PASSWORD"),
    "langfuse": ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"),
    "pioneer": ("PIONEER_API_KEY",),
    "senso": ("SENSO_API_KEY",),
    "airbyte": ("AIRBYTE_CLIENT_ID", "AIRBYTE_CLIENT_SECRET"),
    "composio": ("COMPOSIO_API_KEY",),
    "guild": ("GUILD_PAT", "GUILD_API_BASE"),
    "anthropic": ("ANTHROPIC_API_KEY",),
}


@app.get("/health")
def health() -> dict[str, Any]:
    dependencies: dict[str, dict[str, Any]] = {}
    for name, env_vars in DEPENDENCY_ENV_VARS.items():
        missing = [v for v in env_vars if not os.environ.get(v, "").strip()]
        dependencies[name] = {
            "status": "blocked" if missing else "configured",
            "missing_env": missing,
        }
    blocked = sorted(n for n, d in dependencies.items() if d["status"] == "blocked")
    return {
        "service": "webhook-api",
        "status": "degraded" if blocked else "ok",
        "blocked": blocked,
        "dependencies": dependencies,
    }
