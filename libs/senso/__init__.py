"""Senso.ai knowledge base client — runbooks, ownership maps, postmortems.

Real REST retrieval lives in libs/senso/retrieve.py (same base-URL
convention as scripts/seed_senso.py: SENSO_BASE_URL override, X-API-Key).
Raises NotConfiguredError naming B6 while SENSO_API_KEY is unset
(BUILD-STATE.md). HARD RULE: responses without a resolvable citation raise
UncitedResponseError — the agent refuses uncited knowledge. A hallucinated
runbook is worse than no runbook.
"""

from __future__ import annotations

from libs.senso.retrieve import (
    CitedDocument,
    NoDocumentFoundError,
    UncitedResponseError,
    get_ownership,
    get_runbook,
)

__all__ = [
    "CitedDocument",
    "NoDocumentFoundError",
    "UncitedResponseError",
    "get_ownership",
    "get_runbook",
]
