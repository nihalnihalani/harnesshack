"""Composio actions — SLACK_SEND_MESSAGE + JIRA_CREATE_ISSUE via session.link().

NEVER use the deprecated initiate() (CLAUDE.md Learned Rules — legacy
endpoints already return 410; cutover 2026-07-03).

Every send goes through the SINGLE choke point in libs/composio_actions/
send.py: GLiGuard screen -> idempotency check -> Composio execute. Raises
NotConfiguredError naming B7 while COMPOSIO_API_KEY is unset
(BUILD-STATE.md). Suggests owners ('Suggested owner — awaiting
confirmation'), never assigns.
"""

from __future__ import annotations

from libs.composio_actions.send import (
    OWNER_SUGGESTION_WORDING,
    BlockedContentError,
    GuardrailBypassError,
    create_jira_followup,
    post_slack_update,
)

__all__ = [
    "OWNER_SUGGESTION_WORDING",
    "BlockedContentError",
    "GuardrailBypassError",
    "create_jira_followup",
    "post_slack_update",
]
