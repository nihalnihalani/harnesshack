"""Composio actions — SLACK_SEND_MESSAGE + JIRA_CREATE_ISSUE via session.link().

NEVER use the deprecated initiate() (CLAUDE.md Learned Rules — legacy
endpoints already return 410; cutover 2026-07-03).

Honest unconfigured state, NOT a mock: raises NotConfiguredError until
COMPOSIO_API_KEY lands (BUILD-STATE.md B7). Real action client lands in
Phase 4 — it suggests owners, never assigns.
"""

from __future__ import annotations

import os
from typing import Any

from libs.errors import NotConfiguredError


def get_composio_client() -> Any:
    if not os.environ.get("COMPOSIO_API_KEY", "").strip():
        raise NotConfiguredError(
            "Composio not configured: set COMPOSIO_API_KEY — see BUILD-STATE.md B7"
        )
    raise NotConfiguredError(
        "Composio credentials detected but the Slack/Jira action client lands in "
        "Phase 4 — see BUILD-STATE.md phase checklist (no fake client is ever returned)"
    )


__all__ = ["get_composio_client"]
