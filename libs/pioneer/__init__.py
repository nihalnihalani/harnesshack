"""Pioneer (Fastino) clients — GLiNER2 extraction + GLiGuard moderation.

GLiNER2 = schema-conditioned extraction/classification (severity, blast
radius). GLiGuard = outbound-text safety moderation. NEVER swap the two
(CLAUDE.md Learned Rules).

Honest unconfigured state, NOT a mock: raises NotConfiguredError until
PIONEER_API_KEY lands (BUILD-STATE.md B4). Real REST clients land in
Phase 3 — and the first live GLiNER2 call MUST record measured latency.
"""

from __future__ import annotations

import os
from typing import Any

from libs.errors import NotConfiguredError


def get_pioneer_client() -> Any:
    if not os.environ.get("PIONEER_API_KEY", "").strip():
        raise NotConfiguredError(
            "Pioneer not configured: set PIONEER_API_KEY — see BUILD-STATE.md B4"
        )
    raise NotConfiguredError(
        "Pioneer credentials detected but the GLiNER2/GLiGuard clients land in "
        "Phase 3 — see BUILD-STATE.md phase checklist (no fake client is ever returned)"
    )


__all__ = ["get_pioneer_client"]
