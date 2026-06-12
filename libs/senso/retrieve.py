"""Senso.ai retrieval — runbooks + ownership, ALWAYS cited.

Real REST client against the same base-URL convention scripts/seed_senso.py
uses: https://sdk.senso.ai/api/v1 (override via SENSO_BASE_URL), X-API-Key
auth. Raises NotConfiguredError naming B6 while SENSO_API_KEY is unset.

HARD RULE (CLAUDE.md: remove Senso -> hallucinated runbooks): a response
without a resolvable citation/source reference raises UncitedResponseError —
the agent REFUSES uncited knowledge. There is no uncited fallback and no
fake document on any path.

ON-SITE CONFIRMATION REQUIRED (B6): Senso's docs are sign-in gated
(sponsors.md). The search endpoint below follows their published REST
conventions (seed_senso.py already pins POST /content/raw for ingestion);
`parse_search_response` is tolerant about container/field spelling but fails
loudly (UnexpectedResponseShapeError / UncitedResponseError) on anything it
cannot resolve. Confirm /search request+response shapes the moment B6 lands.
"""

from __future__ import annotations

import dataclasses
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

import httpx

from libs.errors import NotConfiguredError, UnexpectedResponseShapeError
from libs.tracing import call_traced

logger = logging.getLogger("incidentsherpa.senso")

DEFAULT_BASE_URL = "https://sdk.senso.ai/api/v1"
SEARCH_PATH = "/search"
_TIMEOUT_SECONDS = 30.0

_RESULTS_KEYS = ("results", "matches", "documents", "hits", "answers", "data")
_CONTENT_KEYS = ("text", "content", "chunk", "answer", "summary")
_SOURCE_ID_KEYS = ("source_id", "content_id", "document_id", "id")
_CITATION_KEYS = ("citation", "source", "title", "reference")


class UncitedResponseError(RuntimeError):
    """Senso returned knowledge without a resolvable citation/source reference.

    The agent refuses uncited knowledge — a runbook step it cannot cite is a
    runbook step it does not have.
    """


class NoDocumentFoundError(LookupError):
    """The query matched no documents (an honest empty result, loudly surfaced)."""


@dataclass(frozen=True)
class CitedDocument:
    """A retrieved document that carries its provenance.

    `latency_ms` is the MEASURED wall-clock of the live HTTP retrieval that
    produced this document (claim integrity: it feeds the UI latency badge).
    It is None for documents parsed outside a live call (e.g. in unit tests
    of the parser) — the badge then says "awaiting measurement", never a
    made-up number.
    """

    content: str
    citation: str
    source_id: str
    latency_ms: float | None = None


def _api_key() -> str:
    key = os.environ.get("SENSO_API_KEY", "").strip()
    if not key:
        raise NotConfiguredError(
            "Senso not configured: set SENSO_API_KEY — see BUILD-STATE.md B6"
        )
    return key


def base_url() -> str:
    return os.environ.get("SENSO_BASE_URL", "").strip() or DEFAULT_BASE_URL


def build_search_request(query: str, max_results: int = 3) -> dict[str, Any]:
    """Build the search request body (shape flagged for on-site confirmation, B6)."""
    return {"query": query, "max_results": max_results}


def _first_result(data: Any) -> dict[str, Any]:
    candidates: list[Any] = []
    if isinstance(data, dict):
        candidates.extend(data.get(key) for key in _RESULTS_KEYS)
        candidates.append(data)  # single-answer shape: {"answer": ..., "source": ...}
    elif isinstance(data, list):
        candidates.append(data)
    for candidate in candidates:
        if isinstance(candidate, list):
            if not candidate:
                raise NoDocumentFoundError(
                    "Senso search returned zero documents for this query — "
                    "seed the knowledge base (scripts/seed_senso.py) or broaden the query"
                )
            candidate = candidate[0]
        if isinstance(candidate, dict) and any(key in candidate for key in _CONTENT_KEYS):
            return candidate
    raise UnexpectedResponseShapeError(
        "Senso search response has no resolvable results container — confirm the "
        f"live /search shape when B6 lands (got: {str(data)[:300]!r})"
    )


def parse_search_response(data: Any) -> CitedDocument:
    """Parse the top search result into a CitedDocument.

    HARD RULE: content without a resolvable citation/source reference raises
    UncitedResponseError — never returned, never defaulted.
    """
    result = _first_result(data)
    content = next(
        (result[key] for key in _CONTENT_KEYS if isinstance(result.get(key), str)), None
    )
    if not content:
        raise UnexpectedResponseShapeError(
            f"Senso result has no resolvable content field — got keys {sorted(result)!r}; "
            "confirm the live /search shape when B6 lands"
        )
    source_id = next(
        (result[key] for key in _SOURCE_ID_KEYS if result.get(key) not in (None, "")), None
    )
    citation = next(
        (
            result[key]
            for key in _CITATION_KEYS
            if isinstance(result.get(key), str) and result[key].strip()
        ),
        None,
    )
    if source_id is None and citation is None:
        raise UncitedResponseError(
            "Senso returned content WITHOUT a resolvable citation/source reference "
            f"(looked for {_SOURCE_ID_KEYS + _CITATION_KEYS}) — the agent refuses "
            "uncited knowledge"
        )
    return CitedDocument(
        content=content,
        citation=citation or f"senso:{source_id}",
        source_id=str(source_id) if source_id is not None else f"citation:{citation}",
    )


def _search(query: str, span_name: str) -> CitedDocument:
    key = _api_key()
    request_body = build_search_request(query)

    def _call() -> tuple[Any, float]:
        start = time.perf_counter()
        response = httpx.post(
            base_url() + SEARCH_PATH,
            json=request_body,
            headers={"X-API-Key": key},
            timeout=_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        latency_ms = (time.perf_counter() - start) * 1000.0  # MEASURED
        return response.json(), latency_ms

    data, latency_ms = call_traced(span_name, _call, logger=logger)
    return dataclasses.replace(parse_search_response(data), latency_ms=latency_ms)


def get_runbook(symptom_query: str) -> CitedDocument:
    """Retrieve the best-matching runbook for a symptom — cited or refused.

    Raises NotConfiguredError (B6) keyless; httpx errors on transport/HTTP
    failure (callers wrap in libs.resilience.with_retries);
    UncitedResponseError when provenance cannot be resolved.
    """
    return _search(f"runbook: {symptom_query}", "senso.get_runbook")


def get_ownership(service: str) -> CitedDocument:
    """Retrieve the ownership map entry for a service — cited or refused.

    The content feeds a SUGGESTION ('Suggested owner — awaiting confirmation');
    nothing here assigns anyone to anything.
    """
    return _search(f"service ownership map: {service}", "senso.get_ownership")


def get_precedents(symptom_query: str) -> CitedDocument:
    """Retrieve the best-matching PAST POSTMORTEM for a symptom — cited or refused.

    Feeds Phase 6 postmortem generation: precedents may only be cited, never
    paraphrased as fact about the CURRENT incident. Same hard rules as every
    other retrieval: NotConfiguredError (B6) keyless, UncitedResponseError on
    uncited content, NoDocumentFoundError on an honest empty result.
    """
    return _search(f"past incident postmortem: {symptom_query}", "senso.get_precedents")


__all__ = [
    "DEFAULT_BASE_URL",
    "SEARCH_PATH",
    "CitedDocument",
    "NoDocumentFoundError",
    "UncitedResponseError",
    "base_url",
    "build_search_request",
    "get_ownership",
    "get_precedents",
    "get_runbook",
    "parse_search_response",
]
