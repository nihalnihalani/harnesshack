"""Guild.ai session client — REST-first per the descope decision (descope.md).

Guild is the control plane: one session per incident, an APPEND-ONLY audit
trail of every typed event, closed on resolve. The event log IS the product;
Guild is its second, governance-grade home (alongside ClickHouse `events`).

Path decision (BUILD-STATE.md DECISIONS 2026-06-12): `@guildai/agents-sdk`
lives on Guild's PRIVATE npm registry (app.guild.ai/npm — 401 without auth),
so this client is REST-first. If a Guild PAT later grants registry access,
the SDK becomes an optional upgrade, not a rewrite. Full rationale in
libs/guild/descope.md.

Auth: `Authorization: Bearer $GUILD_PAT` against `$GUILD_API_BASE`. Raises
NotConfiguredError naming B1 while either is unset. Never returns fake
sessions or fake audit entries on any path.

ON-SITE CONFIRMATION REQUIRED (B1): endpoint paths follow the descope-doc
convention — POST /v1/sessions, POST /v1/sessions/{id}/events,
POST /v1/sessions/{id}/close. Guild's REST docs were not publicly
verifiable at authoring time (open beta, sponsors.md); confirm paths and
response field names with the Guild rep the moment B1 lands. The
session-id parse is tolerant about field spelling but fails loudly
(UnexpectedResponseShapeError) — it never invents a session id.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from libs.errors import NotConfiguredError, UnexpectedResponseShapeError
from libs.tracing import call_traced

logger = logging.getLogger("incidentsherpa.guild")

SESSIONS_PATH = "/v1/sessions"
_TIMEOUT_SECONDS = 30.0
_SESSION_ID_KEYS = ("id", "session_id", "sessionId")


def _config() -> tuple[str, str]:
    """(base_url, pat) from env — NotConfiguredError naming B1 when missing."""
    base = os.environ.get("GUILD_API_BASE", "").strip().rstrip("/")
    pat = os.environ.get("GUILD_PAT", "").strip()
    missing = [
        name
        for name, value in (("GUILD_PAT", pat), ("GUILD_API_BASE", base))
        if not value
    ]
    if missing:
        raise NotConfiguredError(
            f"Guild not configured: set {', '.join(missing)} — see BUILD-STATE.md B1"
        )
    return base, pat


def _headers(pat: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {pat}"}


def build_session_request(incident_id: str) -> dict[str, Any]:
    """Request body for POST /v1/sessions (shape flagged for on-site confirmation)."""
    return {
        "name": f"incident-{incident_id}",
        "metadata": {"incident_id": incident_id, "agent": "incident-sherpa"},
    }


def build_audit_event_payload(typed_event: Any) -> dict[str, Any]:
    """Serialize a TypedEvent (duck-typed: ts/incident_id/event_type/payload).

    Duck-typed instead of importing apps.worker.agent to keep the libs->apps
    dependency direction clean (apps.worker.agent imports this module).
    """
    return {
        "ts": typed_event.ts.isoformat(),
        "incident_id": typed_event.incident_id,
        "event_type": typed_event.event_type,
        "payload": typed_event.payload,
    }


def _parse_session_id(data: Any) -> str:
    candidates: list[Any] = [data]
    if isinstance(data, dict):
        candidates.append(data.get("data"))
        candidates.append(data.get("session"))
    for candidate in candidates:
        if isinstance(candidate, dict):
            for key in _SESSION_ID_KEYS:
                value = candidate.get(key)
                if isinstance(value, str | int) and str(value).strip():
                    return str(value)
    raise UnexpectedResponseShapeError(
        "Guild session-create response has no resolvable session id — confirm the "
        f"live response shape when B1 lands (got: {str(data)[:300]!r})"
    )


def create_session(incident_id: str) -> str:
    """POST /v1/sessions — one Guild session per incident; returns session_id.

    Raises NotConfiguredError (B1) keyless; httpx errors on transport/HTTP
    failure (callers wrap in libs.resilience.with_retries). Langfuse-traced.
    """
    base, pat = _config()

    def _call() -> Any:
        response = httpx.post(
            base + SESSIONS_PATH,
            json=build_session_request(incident_id),
            headers=_headers(pat),
            timeout=_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()

    data = call_traced("guild.create_session", _call, logger=logger)
    return _parse_session_id(data)


def append_audit_event(session_id: str, typed_event: Any) -> None:
    """POST /v1/sessions/{id}/events — append ONE typed event to the audit log.

    Append-only by construction: there is no update or delete in this module.
    """
    base, pat = _config()
    payload = build_audit_event_payload(typed_event)

    def _call() -> None:
        response = httpx.post(
            f"{base}{SESSIONS_PATH}/{session_id}/events",
            json=payload,
            headers=_headers(pat),
            timeout=_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

    call_traced("guild.append_audit_event", _call, logger=logger)


def close_session(session_id: str) -> None:
    """POST /v1/sessions/{id}/close — close the incident's Guild session."""
    base, pat = _config()

    def _call() -> None:
        response = httpx.post(
            f"{base}{SESSIONS_PATH}/{session_id}/close",
            headers=_headers(pat),
            timeout=_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

    call_traced("guild.close_session", _call, logger=logger)


__all__ = [
    "SESSIONS_PATH",
    "append_audit_event",
    "build_audit_event_payload",
    "build_session_request",
    "close_session",
    "create_session",
]
