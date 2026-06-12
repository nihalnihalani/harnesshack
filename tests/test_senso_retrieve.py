"""Senso retrieval tests — request shape, citation hard rule, keyless honesty.

No credentials, no network: real builders/parsers of libs/senso/retrieve.py
against the VERIFIED-LIVE apiv2 /org/search contract. The fixtures below are
captured from real live calls (2026-06-13): an `answer` string plus a
`results[]` list whose items carry chunk_text / title / content_id / score.
"""

from __future__ import annotations

import pytest

from libs.errors import NotConfiguredError, UnexpectedResponseShapeError
from libs.senso.retrieve import (
    DEFAULT_BASE_URL,
    NoDocumentFoundError,
    UncitedResponseError,
    base_url,
    build_search_request,
    get_ownership,
    get_precedents,
    get_runbook,
    parse_search_response,
)

# A captured live /org/search response (the grounded `answer` + a results[]
# entry carrying the fields the real apiv2 returns).
LIVE_HIT = {
    "query": "runbook: payments p99 latency breach",
    "answer": (
        "# Payments p99 latency breach\n\n"
        "**Symptom:** `payments-service p99_ms` breaches the **2400ms** threshold.\n\n"
        "## Steps\n1. Confirm blast radius via the causal graph.\n"
        "2. Check `payments-db-primary` `pool_used` vs `pool_max 100`.\n"
        "3. Raise DB connection pool ceiling from **100 to 150**."
    ),
    "results": [
        {
            "content_id": "6cff5947-9f1e-430e-9e8b-c9eedfc4f15a",
            "version_id": "v1",
            "chunk_index": 0,
            "chunk_text": "# Payments p99 Runbook\n\nSymptom: payments p99 breaches 2400ms.",
            "score": 0.5429472923278809,
            "rank": 1,
            "title": "payments-p99-runbook.md",
            "vector_id": "vec_1",
            "source_type": "kb",
            "content_type": "text/markdown",
        }
    ],
    "total_results": 1,
    "max_results": 3,
    "processing_time_ms": 421,
}

# A captured live no-match response.
LIVE_EMPTY = {
    "query": "zzzqqq nonexistent topic xyzzy",
    "answer": "No results found for your query.",
    "results": [],
    "total_results": 0,
    "max_results": 3,
    "processing_time_ms": 88,
}


class TestKeyless:
    def test_get_runbook_raises_b6(self):
        with pytest.raises(NotConfiguredError, match="B6"):
            get_runbook("payments p99 breach")

    def test_get_ownership_raises_b6(self):
        with pytest.raises(NotConfiguredError, match="B6"):
            get_ownership("payments-service")

    def test_get_precedents_raises_b6(self):
        with pytest.raises(NotConfiguredError, match="B6"):
            get_precedents("payments p99 breach pool exhaustion")


class TestRequestShape:
    def test_query_and_max_results(self):
        assert build_search_request("pool exhaustion", max_results=2) == {
            "query": "pool exhaustion",
            "max_results": 2,
        }

    def test_base_url_is_verified_live_apiv2(self, monkeypatch: pytest.MonkeyPatch):
        # VERIFIED-LIVE: default apiv2.senso.ai/api/v1, SENSO_BASE_URL override.
        assert base_url() == DEFAULT_BASE_URL == "https://apiv2.senso.ai/api/v1"
        monkeypatch.setenv("SENSO_BASE_URL", "https://staging.senso.test/api/v1")
        assert base_url() == "https://staging.senso.test/api/v1"


class TestCitationHardRule:
    def test_live_hit_parses_with_grounded_answer_and_citation(self):
        doc = parse_search_response(LIVE_HIT)
        # Content is the grounded synthesized answer, not the raw chunk.
        assert doc.content.startswith("# Payments p99 latency breach")
        # Citation derives from results[0]: "<title> (<content_id>)".
        assert doc.citation == (
            "payments-p99-runbook.md (6cff5947-9f1e-430e-9e8b-c9eedfc4f15a)"
        )
        assert doc.source_id == "6cff5947-9f1e-430e-9e8b-c9eedfc4f15a"

    def test_no_match_is_honest_empty(self):
        with pytest.raises(NoDocumentFoundError):
            parse_search_response(LIVE_EMPTY)

    def test_empty_results_list_fails_loudly(self):
        with pytest.raises(NoDocumentFoundError):
            parse_search_response(
                {"answer": "anything", "results": [], "total_results": 0}
            )

    def test_answer_without_citable_source_is_refused(self):
        # An answer with a result that carries NEITHER title NOR content_id
        # cannot be cited -> the agent refuses uncited knowledge.
        with pytest.raises(UncitedResponseError):
            parse_search_response(
                {
                    "answer": "raise the pool ceiling to 150",
                    "results": [{"chunk_text": "raise the ceiling", "score": 0.4}],
                    "total_results": 1,
                }
            )

    def test_title_only_result_is_citable(self):
        doc = parse_search_response(
            {
                "answer": "body answer",
                "results": [{"title": "INC-2417 postmortem", "chunk_text": "x"}],
                "total_results": 1,
            }
        )
        assert doc.citation == "INC-2417 postmortem"
        assert doc.source_id == "citation:INC-2417 postmortem"

    def test_content_id_only_result_is_citable(self):
        doc = parse_search_response(
            {
                "answer": "body answer",
                "results": [{"content_id": "c9", "chunk_text": "x"}],
                "total_results": 1,
            }
        )
        assert doc.source_id == "c9"
        assert doc.citation == "senso:c9"

    def test_chunk_text_fallback_when_answer_blank(self):
        doc = parse_search_response(
            {
                "answer": "",
                "results": [{"content_id": "c1", "title": "t.md", "chunk_text": "the chunk body"}],
                "total_results": 1,
            }
        )
        assert doc.content == "the chunk body"
        assert doc.citation == "t.md (c1)"

    def test_missing_answer_key_fails_loudly(self):
        with pytest.raises(UnexpectedResponseShapeError):
            parse_search_response({"results": [{"content_id": "c1"}], "total_results": 1})

    def test_non_object_fails_loudly(self):
        with pytest.raises(UnexpectedResponseShapeError):
            parse_search_response(["not", "an", "object"])


class TestLatencyClaimIntegrity:
    def test_parser_alone_never_invents_a_latency(self):
        # latency_ms is the MEASURED wall clock of a live call; the pure
        # parser has no measurement, so it must be None — never a number.
        doc = parse_search_response(LIVE_HIT)
        assert doc.latency_ms is None
