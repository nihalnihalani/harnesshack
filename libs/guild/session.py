"""Guild.ai session client — VERIFIED-LIVE REST contract (confirmed 2026-06-13).

Guild is the control plane: one session per incident, an APPEND-ONLY audit
trail of every typed event. The event log IS the product; Guild is its
second, governance-grade home (alongside ClickHouse `events`).

Path decision (BUILD-STATE.md, firings 18-19): Guild has NO standalone REST
sessions API on its public host, and the `@guildai/agents-sdk` is TypeScript.
The control-plane REST API the official `guild` CLI uses IS reachable, and is
what we drive here directly (fast — no subprocess per event):

  Base : https://app.guild.ai/api
  Auth : Authorization: Bearer <token>, where the token is GUILD_TOKEN if set,
         else the output of `guild auth token` (the CLI's stored session token
         after a one-time `guild auth login`). NOT the GUILD_PAT (that only
         reaches the Agent Hub browse API).
  Create: POST /workspaces/{workspace_id}/sessions
          body {"session_type":"chat","initial_prompt": <text>} -> 201 {id,...}
  Append: POST /sessions/{session_id}/events
          body {"content": <event dict>, "mode":"json"} -> 201
  Read  : GET  /sessions/{session_id}/events?limit=N -> 200 {items:[...]}

Config: GUILD_WORKSPACE (workspace UUID) is required; the token comes from
GUILD_TOKEN or `guild auth token`. Raises NotConfiguredError naming B1 when
unconfigured/unauthenticated. Never returns fake sessions or fake audit
entries on any path.

Render/headless note: a server cannot run `guild auth login`; set GUILD_TOKEN
in the environment there (a token captured from `guild auth token`).
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from functools import lru_cache
from typing import Any

import httpx

from libs.errors import NotConfiguredError, UnexpectedResponseShapeError
from libs.tracing import call_traced

logger = logging.getLogger("incidentsherpa.guild")

API_BASE = "https://app.guild.ai/api"
_TIMEOUT_SECONDS = 30.0
_SESSION_ID_KEYS = ("id", "session_id", "sessionId")


@lru_cache(maxsize=1)
def _auth_token() -> str:
    """Bearer token: GUILD_TOKEN env, else `guild auth token` (cached per process).

    Raises NotConfiguredError(B1) when neither is available — e.g. the CLI is
    not installed or `guild auth login` has not been run. Never fabricates one.
    """
    env_token = os.environ.get("GUILD_TOKEN", "").strip()
    if env_token:
        return env_token
    cli = shutil.which("guild")
    if cli:
        try:
            out = subprocess.run(
                [cli, "auth", "token"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            token = out.stdout.strip()
            if out.returncode == 0 and token and not token.lower().startswith("✗"):
                return token
        except (subprocess.SubprocessError, OSError) as exc:  # pragma: no cover
            logger.warning("guild auth token failed: %s", exc)
    raise NotConfiguredError(
        "Guild not authenticated: set GUILD_TOKEN, or run `guild auth login` so "
        "`guild auth token` works — see BUILD-STATE.md B1"
    )


def _workspace() -> str:
    ws = os.environ.get("GUILD_WORKSPACE", "").strip()
    if not ws:
        raise NotConfiguredError(
            "Guild not configured: set GUILD_WORKSPACE (workspace UUID) — see BUILD-STATE.md B1"
        )
    return ws


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_auth_token()}", "Content-Type": "application/json"}


def build_session_request(incident_id: str) -> dict[str, Any]:
    """Body for POST /workspaces/{ws}/sessions (verified-live shape)."""
    return {
        "session_type": "chat",
        "initial_prompt": f"IncidentSherpa audit session for incident {incident_id}",
    }


def build_audit_event_payload(typed_event: Any) -> dict[str, Any]:
    """Wrap a TypedEvent as the verified-live append body {content, mode:json}.

    Duck-typed (ts/incident_id/event_type/payload) to keep libs independent of
    apps.worker.agent, which imports this module.
    """
    return {
        "content": {
            "ts": typed_event.ts.isoformat(),
            "incident_id": typed_event.incident_id,
            "event_type": typed_event.event_type,
            "payload": typed_event.payload,
        },
        "mode": "json",
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
        f"Guild session-create response has no resolvable session id (got: {str(data)[:300]!r})"
    )


def create_session(incident_id: str) -> str:
    """POST /workspaces/{ws}/sessions — one Guild session per incident; returns id.

    Raises NotConfiguredError (B1) keyless/unauthenticated; httpx errors on
    transport/HTTP failure (callers wrap in libs.resilience.with_retries).
    Langfuse-traced.
    """
    ws = _workspace()

    def _call() -> Any:
        response = httpx.post(
            f"{API_BASE}/workspaces/{ws}/sessions",
            json=build_session_request(incident_id),
            headers=_headers(),
            timeout=_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()

    data = call_traced("guild.create_session", _call, logger=logger)
    return _parse_session_id(data)


def append_audit_event(session_id: str, typed_event: Any) -> None:
    """POST /sessions/{id}/events — append ONE typed event to the audit log.

    Append-only by construction: no update or delete exists in this module.
    """
    payload = build_audit_event_payload(typed_event)

    def _call() -> None:
        response = httpx.post(
            f"{API_BASE}/sessions/{session_id}/events",
            json=payload,
            headers=_headers(),
            timeout=_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

    call_traced("guild.append_audit_event", _call, logger=logger)


def read_audit_events(session_id: str, limit: int = 1000) -> list[dict[str, Any]]:
    """GET /sessions/{id}/events — read the audit trail back (for verification)."""

    def _call() -> Any:
        response = httpx.get(
            f"{API_BASE}/sessions/{session_id}/events",
            params={"limit": limit},
            headers=_headers(),
            timeout=_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()

    data = call_traced("guild.read_audit_events", _call, logger=logger)
    if isinstance(data, dict):
        return data.get("items", [])
    return data if isinstance(data, list) else []


def close_session(session_id: str) -> None:
    """No-op: the Guild session API has no close endpoint; the audit trail is
    append-only and persists. Kept for interface symmetry with the agent's
    lifecycle. The session remains readable via read_audit_events.
    """
    return None


__all__ = [
    "API_BASE",
    "append_audit_event",
    "build_audit_event_payload",
    "build_session_request",
    "close_session",
    "create_session",
    "read_audit_events",
]
