"""Guild.ai control plane client — REST descope path (DECISIONS 2026-06-12).

Honest unconfigured state, NOT a mock: the factory raises NotConfiguredError
until GUILD_PAT / GUILD_API_BASE land (BUILD-STATE.md B1). It never returns
fake sessions or fake audit entries. Real session/audit REST client lands in
Phase 3.
"""

from __future__ import annotations

import os
from typing import Any

from libs.errors import NotConfiguredError

_REQUIRED_ENV = ("GUILD_PAT", "GUILD_API_BASE")


def get_guild_client() -> Any:
    missing = [key for key in _REQUIRED_ENV if not os.environ.get(key, "").strip()]
    if missing:
        raise NotConfiguredError(
            f"Guild not configured: set {', '.join(missing)} — see BUILD-STATE.md B1"
        )
    raise NotConfiguredError(
        "Guild credentials detected but the REST session client lands in Phase 3 "
        "— see BUILD-STATE.md phase checklist (no fake client is ever returned)"
    )


__all__ = ["get_guild_client"]
