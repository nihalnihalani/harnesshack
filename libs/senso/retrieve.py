"""Senso.ai retrieval — runbooks + ownership, ALWAYS cited.

Real REST client against the VERIFIED-LIVE apiv2 contract (confirmed by live
calls 2026-06-13): base URL https://apiv2.senso.ai/api/v1 (override via
SENSO_BASE_URL), X-API-Key auth (keys are `tgr_`-prefixed — that is valid).
Raises NotConfiguredError naming B6 while SENSO_API_KEY is unset.

HARD RULE (CLAUDE.md: remove Senso -> hallucinated runbooks): a response
without a resolvable citation/source raises UncitedResponseError — the agent
REFUSES uncited knowledge. There is no uncited fallback and no fake document
on any path.

VERIFIED-LIVE SEARCH CONTRACT:
    POST /org/search  body {"query": <str>, "max_results": <int optional>}
    -> {"query":..., "answer":"<AI-synthesized grounded answer>",
        "results":[{content_id, version_id, chunk_index, chunk_text, score,
                    rank, title, vector_id, source_type, content_type}],
        "total_results":<int>, "max_results":<int>, "processing_time_ms":<int>}
    No match -> answer="No results found for your query.", results=[],
    total_results=0.

We prefer `answer` (the grounded synthesis) as the document content and derive
the citation/source from results[0] (title + content_id). total_results==0 /
empty results -> NoDocumentFoundError (honest empty); an answer with NO result
to cite -> UncitedResponseError (never return uncited knowledge).
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

DEFAULT_BASE_URL = "https://apiv2.senso.ai/api/v1"
SEARCH_PATH = "/org/search"
_TIMEOUT_SECONDS = 60.0

# The grounded-synthesis answer Senso returns when the KB has no match.
_NO_MATCH_ANSWER = "No results found for your query."


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
    """Build the VERIFIED-LIVE /org/search request body."""
    return {"query": query, "max_results": max_results}


def parse_search_response(data: Any) -> CitedDocument:
    """Parse a VERIFIED-LIVE /org/search response into a CitedDocument.

    Prefers `answer` (the AI-synthesized grounded answer) as the content and
    derives the citation/source from results[0] (title + content_id).

    HARD RULES:
    - total_results == 0 / empty results -> NoDocumentFoundError (honest empty).
    - an answer exists but there is NO result/source to cite ->
      UncitedResponseError (the agent refuses uncited knowledge).
    """
    if not isinstance(data, dict):
        raise UnexpectedResponseShapeError(
            "Senso /org/search returned a non-object response — "
            f"expected a JSON object (got: {str(data)[:300]!r})"
        )

    results = data.get("results")
    total_results = data.get("total_results")
    answer = data.get("answer")

    if results is None or "answer" not in data:
        raise UnexpectedResponseShapeError(
            "Senso /org/search response missing 'answer'/'results' — "
            f"got keys {sorted(data)!r} (confirm the apiv2 contract)"
        )

    # Honest empty: no documents matched (explicit count OR the no-match answer).
    if not results or total_results == 0 or answer == _NO_MATCH_ANSWER:
        raise NoDocumentFoundError(
            "Senso search returned zero documents for this query — "
            "seed the knowledge base (scripts/seed_senso.py) or broaden the query"
        )

    if not isinstance(results, list) or not isinstance(results[0], dict):
        raise UnexpectedResponseShapeError(
            "Senso /org/search 'results' is not a list of objects — "
            f"got {str(results)[:300]!r}"
        )

    top = results[0]
    content_id = top.get("content_id")
    title = top.get("title")

    # Content: prefer the grounded synthesized answer; fall back to the top
    # chunk_text only if the answer is missing (never invent content).
    content = answer if isinstance(answer, str) and answer.strip() else None
    if content is None:
        chunk = top.get("chunk_text")
        content = chunk if isinstance(chunk, str) and chunk.strip() else None
    if not content:
        raise UnexpectedResponseShapeError(
            "Senso /org/search returned a result with no resolvable content "
            f"(no 'answer' and no 'chunk_text') — got result keys {sorted(top)!r}"
        )

    # Provenance: derive from results[0]. Without it we cannot cite -> refuse.
    if content_id in (None, "") and (not isinstance(title, str) or not title.strip()):
        raise UncitedResponseError(
            "Senso returned an answer WITHOUT a resolvable citation/source "
            "(results[0] has neither content_id nor title) — the agent refuses "
            "uncited knowledge"
        )

    title_str = title.strip() if isinstance(title, str) and title.strip() else None
    if title_str and content_id:
        citation = f"{title_str} ({content_id})"
    elif title_str:
        citation = title_str
    else:
        citation = f"senso:{content_id}"

    source_id = str(content_id) if content_id not in (None, "") else f"citation:{title_str}"

    return CitedDocument(content=content, citation=citation, source_id=source_id)


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
