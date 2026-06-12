"""Senso.ai knowledge base client — runbooks, ownership maps, postmortems.

Honest unconfigured state, NOT a mock: raises NotConfiguredError until
SENSO_API_KEY lands (BUILD-STATE.md B6). It never returns fake runbooks —
a hallucinated runbook is worse than no runbook. Real REST client (with
mandatory citations) lands in Phase 3.
"""

from __future__ import annotations

import os
from typing import Any

from libs.errors import NotConfiguredError


def get_senso_client() -> Any:
    if not os.environ.get("SENSO_API_KEY", "").strip():
        raise NotConfiguredError(
            "Senso not configured: set SENSO_API_KEY — see BUILD-STATE.md B6"
        )
    raise NotConfiguredError(
        "Senso credentials detected but the retrieval client lands in Phase 3 "
        "— see BUILD-STATE.md phase checklist (no fake client is ever returned)"
    )


__all__ = ["get_senso_client"]
