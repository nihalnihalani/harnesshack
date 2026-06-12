"""Pioneer (Fastino) clients — GLiNER2 extraction + GLiGuard moderation.

GLiNER2 = schema-conditioned extraction/classification (severity, blast
radius) — libs/pioneer/gliner2.py. GLiGuard = outbound-text safety
moderation — libs/pioneer/gliguard.py. NEVER swap the two (CLAUDE.md
Learned Rules).

Both clients are REAL REST code against POST https://api.pioneer.ai/inference
and raise NotConfiguredError naming B4 while PIONEER_API_KEY is unset
(BUILD-STATE.md). No fake data on any path. Response-shape field names are
flagged for on-site confirmation when B4 lands (see module docstrings).
"""

from __future__ import annotations

from libs.pioneer.gliguard import ScreenResult, screen
from libs.pioneer.gliner2 import SeverityExtraction, extract_severity

__all__ = ["ScreenResult", "SeverityExtraction", "extract_severity", "screen"]
