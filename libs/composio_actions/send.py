"""The SINGLE outbound-action choke point — every send is screened, deduped, audited.

Module-structure enforcement (tested in tests/test_choke_point.py): the ONLY
function that touches the Composio session is `_screened_send`, and the ONLY
public senders are `post_slack_update` and `create_jira_followup`, both of
which can ONLY send through `_screened_send`. There is no other send path.

`_screened_send(action, text, idempotency_scope)` pipeline:
  (a) GLiGuard safety screen (libs/pioneer/gliguard — moderation, NEVER
      severity classification; CLAUDE.md Learned Rules), wrapped in
      with_retries. A refusal emits a BLOCKED_BY_GUARDRAIL event and raises
      BlockedContentError. A screener that does not return a real
      ScreenResult raises GuardrailBypassError — no screen, no send.
  (b) Idempotency check per incident_id+state+action. In-process registry
      for now; ClickHouse-backed durable dedupe (events-table lookup)
      replaces it when B2 lands.
  (c) Execution via the Composio SDK: `client.tools.execute(slug,
      arguments=..., user_id=...)`. Connections are pre-authorized once with
      `connected_accounts.link()` / `toolkits.authorize()` (run
      scripts/composio_link.py at the T+0:10 gate) — NEVER the deprecated
      `initiate()` (legacy endpoints already 410; cutover 2026-07-03).

Owner wording (claim integrity): outbound text says
"Suggested owner — awaiting confirmation" — never "assigned". Humans
confirm; the agent recommends.

Raises NotConfiguredError naming B7 while COMPOSIO_API_KEY is unset. Never
fakes a send result on any path.

CONTRACT VERIFIED (B7, 2026-06-12) against the INSTALLED SDK (composio
0.13.1 / core 1.0.0-rc2): there is NO per-call "session" — `tools`,
`connected_accounts`, `toolkits` all hang off the `Composio` instance, and
`tools.execute(slug, arguments, *, user_id=...)` routes to the user's
connected account by `user_id`. The earlier `session.create()/session.link()`
authoring was wrong (introspected signatures). The SLACK_SEND_MESSAGE /
JIRA_CREATE_ISSUE argument field names below still follow the documented
pattern — scripts/composio_link.py prints each tool's live input schema so
they can be confirmed the moment the key + OAuth land.
"""

from __future__ import annotations

import logging
import os
import tempfile
from collections.abc import Callable
from functools import partial
from typing import Any

from libs.errors import NotConfiguredError
from libs.pioneer.gliguard import ScreenResult, screen
from libs.resilience import with_retries
from libs.tracing import call_traced

logger = logging.getLogger("incidentsherpa.composio")

OWNER_SUGGESTION_WORDING = "Suggested owner — awaiting confirmation"

SLACK_ACTION = "SLACK_SEND_MESSAGE"
JIRA_ACTION = "JIRA_CREATE_ISSUE"

EmitFn = Callable[[str, dict[str, Any]], Any]


class BlockedContentError(RuntimeError):
    """GLiGuard refused the outbound text — it was NOT sent."""

    def __init__(self, action: str, categories: tuple[str, ...]) -> None:
        super().__init__(
            f"GLiGuard blocked outbound {action} content (categories: "
            f"{', '.join(categories) or 'unspecified'}) — nothing was sent"
        )
        self.action = action
        self.categories = categories


class GuardrailBypassError(RuntimeError):
    """The screener did not produce a real ScreenResult — sending is refused.

    No screen verdict means NO send, ever. This is the choke point's
    self-defense against a miswired or bypassed guardrail.
    """


# Idempotency registry: (idempotency_scope, action) pairs already sent by
# THIS process. Registered only AFTER a successful execute so a failed send
# stays retryable. ClickHouse-backed durable dedupe (query the `events`
# table for a prior action.executed row) replaces this when B2 lands.
_sent_registry: set[tuple[str, str]] = set()


def reset_idempotency_registry() -> None:
    """Forget in-process dedupe state (test isolation)."""
    _sent_registry.clear()


def _default_screener(text: str) -> ScreenResult:
    """GLiGuard screen under with_retries — transient failures retried,
    exhaustion surfaces as DegradedError (never an implicit pass)."""
    return with_retries(partial(screen, text), service="pioneer-gliguard")


def _composio_user_id() -> str:
    """The Composio user_id that owns the Slack/Jira connected accounts.

    MUST match the user_id scripts/composio_link.py authorized with —
    tools.execute routes to a connected account by this id.
    """
    return os.environ.get("COMPOSIO_USER_ID", "").strip() or "incident-sherpa"


def _get_client() -> Any:
    """Real Composio SDK client — NotConfiguredError naming B7 keyless.

    Returns the `Composio` instance itself (the verified SDK has NO per-call
    session). Connections were pre-authorized via
    `connected_accounts.link()` / `toolkits.authorize()` for Slack
    (chat:write) and Jira (create) at the T+0:10 gate. NEVER call the
    deprecated `initiate()`.
    """
    api_key = os.environ.get("COMPOSIO_API_KEY", "").strip()
    if not api_key:
        raise NotConfiguredError(
            "Composio not configured: set COMPOSIO_API_KEY — see BUILD-STATE.md B7"
        )
    # The SDK writes a cache to ~/.composio at import; pin it to a guaranteed
    # writable dir so a read-only home (some container runtimes) can't crash
    # the import. Honor an explicit COMPOSIO_CACHE_DIR if the operator set one.
    os.environ.setdefault(
        "COMPOSIO_CACHE_DIR", os.path.join(tempfile.gettempdir(), "composio-cache")
    )
    # Imported lazily so the unconfigured path has zero side effects.
    from composio import Composio

    return Composio(api_key=api_key)


def _action_arguments(action: str, text: str) -> dict[str, Any]:
    """Per-action argument shapes (field names flagged for B7 confirmation)."""
    if action == SLACK_ACTION:
        channel = os.environ.get("SLACK_INCIDENT_CHANNEL", "").strip() or "#incidents"
        return {"channel": channel, "text": text}
    if action == JIRA_ACTION:
        summary = text.splitlines()[0][:255]
        project_key = os.environ.get("JIRA_PROJECT_KEY", "").strip() or "INC"
        return {
            "project_key": project_key,
            "issue_type": "Task",
            "summary": summary,
            "description": text,
        }
    raise ValueError(f"Unknown action {action!r}: this choke point only sends "
                     f"{SLACK_ACTION} and {JIRA_ACTION}")


def _screened_send(
    action: str,
    text: str,
    idempotency_scope: str,
    *,
    screener: Callable[[str], ScreenResult] | None = None,
    emit: EmitFn | None = None,
) -> dict[str, Any]:
    """THE choke point. Screen -> dedupe -> execute. No other send path exists."""
    screener = screener or _default_screener
    result = screener(text)
    if not isinstance(result, ScreenResult):
        raise GuardrailBypassError(
            f"screener returned {type(result).__name__!r} instead of a ScreenResult "
            "— no screen verdict means NO send"
        )
    if not result.allowed:
        if emit is not None:
            emit(
                "BLOCKED_BY_GUARDRAIL",
                {
                    "action": action,
                    "categories": list(result.categories),
                    "screen_latency_ms": result.latency_ms,  # MEASURED
                },
            )
        raise BlockedContentError(action, result.categories)

    registry_key = (idempotency_scope, action)
    if registry_key in _sent_registry:
        # Honest dedupe marker — nothing was sent, nothing is faked.
        return {
            "status": "duplicate",
            "action": action,
            "idempotency_scope": idempotency_scope,
        }

    client = _get_client()  # NotConfiguredError (B7) keyless
    user_id = _composio_user_id()

    def _execute() -> Any:
        return client.tools.execute(
            action, arguments=_action_arguments(action, text), user_id=user_id
        )

    response = call_traced(
        f"composio.execute.{action}",
        lambda: with_retries(_execute, service="composio"),
        logger=logger,
    )
    _sent_registry.add(registry_key)
    if emit is not None:
        emit(
            "action.executed",
            {
                "action": action,
                "idempotency_scope": idempotency_scope,
                "screen_latency_ms": result.latency_ms,
            },
        )
    return {"status": "sent", "action": action, "response": response}


def build_slack_update_text(
    incident: Any, causal_summary: str, suggested_owner: str
) -> str:
    """Structured Slack update — suggestion wording enforced, never 'assigned'."""
    return (
        f":rotating_light: Incident {incident.incident_id} — state: {incident.state}\n"
        f"Causal chain: {causal_summary}\n"
        f"{OWNER_SUGGESTION_WORDING}: {suggested_owner}"
    )


def build_jira_followup_text(incident: Any, owner_suggestion: str) -> str:
    """Jira follow-up body — suggestion wording enforced, never 'assigned'."""
    return (
        f"Follow-up for incident {incident.incident_id} (state: {incident.state})\n\n"
        f"{OWNER_SUGGESTION_WORDING}: {owner_suggestion}\n"
        "A human must confirm ownership before any assignment happens."
    )


def post_slack_update(
    incident: Any,
    causal_summary: str,
    suggested_owner: str,
    *,
    screener: Callable[[str], ScreenResult] | None = None,
    emit: EmitFn | None = None,
) -> dict[str, Any]:
    """GLiGuard-screened structured Slack update. Sends ONLY via _screened_send."""
    text = build_slack_update_text(incident, causal_summary, suggested_owner)
    return _screened_send(
        SLACK_ACTION,
        text,
        idempotency_scope=f"{incident.incident_id}:{incident.state}",
        screener=screener,
        emit=emit,
    )


def create_jira_followup(
    incident: Any,
    owner_suggestion: str,
    *,
    screener: Callable[[str], ScreenResult] | None = None,
    emit: EmitFn | None = None,
) -> dict[str, Any]:
    """GLiGuard-screened Jira follow-up. Sends ONLY via _screened_send."""
    text = build_jira_followup_text(incident, owner_suggestion)
    return _screened_send(
        JIRA_ACTION,
        text,
        idempotency_scope=f"{incident.incident_id}:{incident.state}",
        screener=screener,
        emit=emit,
    )


# The complete public surface: two senders, two pure text builders, the
# errors, the wording constant, and the test-isolation reset. _screened_send
# and _get_session stay private — the underscore is the contract, the
# choke-point test is the enforcement.
__all__ = [
    "JIRA_ACTION",
    "OWNER_SUGGESTION_WORDING",
    "SLACK_ACTION",
    "BlockedContentError",
    "GuardrailBypassError",
    "build_jira_followup_text",
    "build_slack_update_text",
    "create_jira_followup",
    "post_slack_update",
    "reset_idempotency_registry",
]
