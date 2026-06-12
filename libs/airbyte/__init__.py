"""Airbyte Agent Engine client — Context Store live query + connector history.

Honest unconfigured state, NOT a mock: raises NotConfiguredError until
AIRBYTE_CLIENT_ID / AIRBYTE_CLIENT_SECRET land (BUILD-STATE.md B5). Real
client (SDK primary, MCP fallback per the T+0:05 gate) lands in Phase 5.
"""

from __future__ import annotations

import os
from typing import Any

from libs.errors import NotConfiguredError

_REQUIRED_ENV = ("AIRBYTE_CLIENT_ID", "AIRBYTE_CLIENT_SECRET")


def get_airbyte_client() -> Any:
    missing = [key for key in _REQUIRED_ENV if not os.environ.get(key, "").strip()]
    if missing:
        raise NotConfiguredError(
            f"Airbyte not configured: set {', '.join(missing)} — see BUILD-STATE.md B5"
        )
    raise NotConfiguredError(
        "Airbyte credentials detected but the Agent Engine client lands in Phase 5 "
        "— see BUILD-STATE.md phase checklist (no fake client is ever returned)"
    )


__all__ = ["get_airbyte_client"]
