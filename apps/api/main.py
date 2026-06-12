"""IncidentSherpa webhook API — alert ingest, SSE stream, resolve/confirm, health.

Endpoints: POST /trigger (idempotent ingest -> IncidentAgent pipeline in the
background), GET /events (SSE), POST /incidents/{id}/resolve (state machine ->
postmortem stream over the bus), POST /incidents/{id}/confirm-owner (human
confirmation as a typed event), GET /fallback/postmortem (the F2 artifact —
404 until a REAL run has cached one), GET /health.

Behavior is honest about its blockers: with CLICKHOUSE_* env vars empty
(BUILD-STATE.md B2), /trigger returns 503 instead of pretending to persist;
a background pipeline hitting an open blocker publishes a visible
SKIPPED_NOT_CONFIGURED event naming it. No mocks, no fake "ok".
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import os
import secrets
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from apps.worker.agent import IllegalTransitionError, IncidentAgent, TypedEvent
from apps.worker.postmortem import (
    FALLBACK_HTML_PATH,
    PostmortemBlockedError,
    generate_postmortem,
    write_fallback_html,
)
from libs.clickhouse import record_event
from libs.errors import NotConfiguredError
from libs.logging_config import configure_logging

# This module IS the webhook-api entrypoint (uvicorn apps.api.main:app) —
# structured JSON-lines logging is configured here, idempotently.
configure_logging()
logger = logging.getLogger("incidentsherpa.api")


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    if not os.environ.get("WEBHOOK_AUTH_TOKEN", "").strip():
        # Loud, structured, and explicit: local dev works keyless, but a
        # production deploy must opt in to that state knowingly.
        logger.warning(
            "webhook auth DISABLED — set WEBHOOK_AUTH_TOKEN in production",
            extra={"security": "webhook_auth", "enabled": False},
        )
    else:
        logger.info(
            "webhook auth enabled — POST /trigger and /incidents/* require a bearer token",
            extra={"security": "webhook_auth", "enabled": True},
        )
    yield


app = FastAPI(title="IncidentSherpa webhook API", version="0.1.0", lifespan=_lifespan)

# Browser clients (the Next.js timeline) consume /events via EventSource and
# POST resolve/confirm cross-origin; without CORS headers the browser blocks
# both. No credentials are exchanged, so a permissive origin is acceptable
# for the demo; override with FRONTEND_ORIGIN in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("FRONTEND_ORIGIN", "").strip() or "*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------
# Webhook security — bearer auth (when WEBHOOK_AUTH_TOKEN is set) and a
# per-IP token bucket on the mutating POST endpoints.
# --------------------------------------------------------------------------

DEFAULT_RATE_LIMIT_PER_MINUTE = 60


def _rate_limit_per_minute() -> int:
    """RATE_LIMIT_PER_MINUTE env (read per request so ops can tune live)."""
    raw = os.environ.get("RATE_LIMIT_PER_MINUTE", "").strip()
    try:
        value = int(raw) if raw else DEFAULT_RATE_LIMIT_PER_MINUTE
    except ValueError:
        logger.warning(
            "invalid RATE_LIMIT_PER_MINUTE — falling back to default",
            extra={"raw_value": raw, "default": DEFAULT_RATE_LIMIT_PER_MINUTE},
        )
        return DEFAULT_RATE_LIMIT_PER_MINUTE
    return max(1, value)


class TokenBucketRateLimiter:
    """In-process per-IP token bucket: capacity == refill == limit/minute.

    Per-process by design (one Render instance per service); a shared store
    is a later-phase concern and would be a new dependency (CLAUDE.md:
    simplicity first).
    """

    def __init__(self) -> None:
        self._buckets: dict[str, tuple[float, float]] = {}  # ip -> (tokens, last_ts)

    def acquire(self, ip: str, limit_per_minute: int, now: float | None = None) -> float | None:
        """Take one token for `ip`. None = allowed; float = Retry-After secs."""
        if now is None:
            now = time.monotonic()
        refill_per_second = limit_per_minute / 60.0
        tokens, last_ts = self._buckets.get(ip, (float(limit_per_minute), now))
        tokens = min(float(limit_per_minute), tokens + (now - last_ts) * refill_per_second)
        if tokens >= 1.0:
            self._buckets[ip] = (tokens - 1.0, now)
            return None
        self._buckets[ip] = (tokens, now)
        return (1.0 - tokens) / refill_per_second

    def reset(self) -> None:
        self._buckets.clear()


_rate_limiter = TokenBucketRateLimiter()


def _is_protected(request: Request) -> bool:
    """POST /trigger and POST /incidents/* mutate state — they are protected."""
    if request.method != "POST":
        return False
    path = request.url.path
    return path == "/trigger" or path.startswith("/incidents/")


@app.middleware("http")
async def webhook_security(request: Request, call_next: Any) -> Any:
    if not _is_protected(request):
        return await call_next(request)

    # 1) Bearer auth — enforced only when WEBHOOK_AUTH_TOKEN is set (the
    #    keyless local-dev state is announced loudly at startup instead).
    expected_token = os.environ.get("WEBHOOK_AUTH_TOKEN", "").strip()
    if expected_token:
        supplied = request.headers.get("Authorization", "")
        expected = f"Bearer {expected_token}"
        if not secrets.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
            logger.warning(
                "rejected unauthenticated request",
                extra={"path": request.url.path, "security": "webhook_auth"},
            )
            return JSONResponse(
                status_code=401,
                content={"detail": "missing or invalid bearer token"},
                headers={"WWW-Authenticate": "Bearer"},
            )

    # 2) Per-IP token bucket.
    client_ip = request.client.host if request.client else "unknown"
    retry_after = _rate_limiter.acquire(client_ip, _rate_limit_per_minute())
    if retry_after is not None:
        retry_after_seconds = max(1, math.ceil(retry_after))
        logger.warning(
            "rate limit exceeded",
            extra={
                "path": request.url.path,
                "client_ip": client_ip,
                "retry_after_seconds": retry_after_seconds,
                "security": "rate_limit",
            },
        )
        return JSONResponse(
            status_code=429,
            content={"detail": "rate limit exceeded — retry later"},
            headers={"Retry-After": str(retry_after_seconds)},
        )

    return await call_next(request)


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


# Per-process registry of live IncidentAgents (incident_id -> agent). The
# resolve/confirm-owner endpoints act on these; a process restart honestly
# loses in-flight agents (404) — durable session resume is a later phase.
_agents: dict[str, IncidentAgent] = {}


def _publish_api_event(incident_id: str, event_type: str, payload: dict[str, Any]) -> None:
    bus.publish(
        {
            "ts": datetime.now(UTC).isoformat(),
            "incident_id": incident_id,
            "event_type": event_type,
            "payload": payload,
        }
    )


def _run_agent_ingest(agent: IncidentAgent, alert_payload: dict[str, Any]) -> None:
    """Background INVESTIGATING pipeline. Failures surface as visible events.

    An open blocker (NotConfiguredError) is published as an honest
    SKIPPED_NOT_CONFIGURED event naming it — the timeline shows exactly what
    is blocked instead of silently doing nothing.
    """
    try:
        agent.ingest_alert(alert_payload)
    except NotConfiguredError as exc:
        _publish_api_event(
            agent.incident_id,
            "SKIPPED_NOT_CONFIGURED",
            {"step": "agent_pipeline", "error": str(exc)},
        )
    except Exception as exc:  # surfaced as a visible event, never swallowed
        # (includes EventLogFatalError — both sinks down is a loud failure)
        logger.exception("agent pipeline failed for %s", agent.incident_id)
        _publish_api_event(
            agent.incident_id,
            "agent.error",
            {"step": "agent_pipeline", "error": f"{type(exc).__name__}: {exc}"},
        )


# --------------------------------------------------------------------------
# POST /trigger — alert ingest
# --------------------------------------------------------------------------


@app.post("/trigger")
async def trigger(
    alert: AlertPayload,
    background_tasks: BackgroundTasks,
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

    # Construct the IncidentAgent and run the INVESTIGATING pipeline in the
    # background (idempotency above guarantees this happens once per alert;
    # a duplicate incident_id on a NEW alert keeps the existing agent).
    agent_started = False
    if incident_id not in _agents:
        agent = IncidentAgent(incident_id)
        _agents[incident_id] = agent
        background_tasks.add_task(_run_agent_ingest, agent, alert.model_dump(mode="json"))
        agent_started = True

    return {
        "duplicate": False,
        "incident_id": incident_id,
        "event_type": event.event_type,
        "agent_started": agent_started,
    }


# --------------------------------------------------------------------------
# POST /incidents/{incident_id}/resolve — human clicks Resolve
# --------------------------------------------------------------------------


async def _stream_postmortem(incident_id: str) -> None:
    """Background postmortem run: tokens stream to the bus from inside
    generate_postmortem; on a clean finish the full text is cached as the F2
    fallback artifact (a REAL run — the only way that file ever exists)."""
    chunks: list[str] = []
    try:
        async for chunk in generate_postmortem(incident_id):
            chunks.append(chunk)
    except NotConfiguredError as exc:
        _publish_api_event(
            incident_id,
            "SKIPPED_NOT_CONFIGURED",
            {"step": "postmortem_generation", "error": str(exc)},
        )
        return
    except PostmortemBlockedError:
        return  # BLOCKED_BY_GUARDRAIL already on the bus; nothing leaked
    except Exception as exc:  # surfaced as a visible event, never swallowed
        logger.exception("postmortem generation failed for %s", incident_id)
        _publish_api_event(
            incident_id,
            "postmortem_error",
            {"error": f"{type(exc).__name__}: {exc}"},
        )
        return
    try:
        write_fallback_html(incident_id, "".join(chunks))
    except Exception:  # the artifact is best-effort; the live run already succeeded
        logger.exception("failed to cache F2 fallback artifact for %s", incident_id)


@app.post("/incidents/{incident_id}/resolve", status_code=202)
def resolve_incident(incident_id: str, background_tasks: BackgroundTasks) -> dict[str, Any]:
    """Human clicks Resolve: MITIGATING -> RESOLVED, then the postmortem
    streams token-by-token over the SSE bus (postmortem_token events)."""
    agent = _agents.get(incident_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"unknown incident {incident_id!r}")
    try:
        agent.resolve(resolved_by="human")
    except IllegalTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except NotConfiguredError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"blocked dependency — see BUILD-STATE.md ({exc})",
        ) from exc
    background_tasks.add_task(_stream_postmortem, incident_id)
    return {"incident_id": incident_id, "state": agent.state, "postmortem": "streaming"}


# --------------------------------------------------------------------------
# POST /incidents/{incident_id}/confirm-owner — human confirmation
# --------------------------------------------------------------------------


class OwnerConfirmation(BaseModel):
    """A HUMAN confirms the suggested owner (the agent only ever suggests)."""

    owner: str = Field(min_length=1)
    confirmed_by: str = Field(default="human", min_length=1)


@app.post("/incidents/{incident_id}/confirm-owner")
def confirm_owner(incident_id: str, confirmation: OwnerConfirmation) -> dict[str, Any]:
    agent = _agents.get(incident_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"unknown incident {incident_id!r}")
    try:
        event = agent.confirm_owner(confirmation.owner, confirmed_by=confirmation.confirmed_by)
    except IllegalTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except NotConfiguredError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"blocked dependency — see BUILD-STATE.md ({exc})",
        ) from exc
    return {"incident_id": incident_id, "event_type": event.event_type, "payload": event.payload}


# --------------------------------------------------------------------------
# GET /fallback/postmortem — the F2 artifact (404 until a REAL run cached one)
# --------------------------------------------------------------------------


@app.get("/fallback/postmortem")
def fallback_postmortem() -> FileResponse:
    """Serve demo_assets/fallback_postmortem.html IF a real run has cached it.

    404 otherwise — the frontend treats that as 'feature disabled'. The file
    is only ever written by write_fallback_html after a live success; there
    is no placeholder on any path.
    """
    if not FALLBACK_HTML_PATH.is_file():
        raise HTTPException(
            status_code=404,
            detail="no fallback postmortem exists yet — it is cached only after a "
            "REAL completed run (never placeholder content)",
        )
    return FileResponse(FALLBACK_HTML_PATH, media_type="text/html")


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
