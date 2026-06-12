"""Senso retrieval tests — request shape, citation hard rule, keyless honesty.

No credentials, no network: real builders/parsers of libs/senso/retrieve.py.
The live /search path is exercised via @pytest.mark.live once B6 lands.
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
    get_runbook,
    parse_search_response,
)


class TestKeyless:
    def test_get_runbook_raises_b6(self):
        with pytest.raises(NotConfiguredError, match="B6"):
            get_runbook("payments p99 breach")

    def test_get_ownership_raises_b6(self):
        with pytest.raises(NotConfiguredError, match="B6"):
            get_ownership("payments-service")


class TestRequestShape:
    def test_query_and_max_results(self):
        assert build_search_request("pool exhaustion", max_results=2) == {
            "query": "pool exhaustion",
            "max_results": 2,
        }

    def test_base_url_matches_seed_senso_convention(self, monkeypatch: pytest.MonkeyPatch):
        # Same convention as scripts/seed_senso.py: default sdk.senso.ai/api/v1,
        # SENSO_BASE_URL override.
        assert base_url() == DEFAULT_BASE_URL
        monkeypatch.setenv("SENSO_BASE_URL", "https://staging.senso.test/api/v1")
        assert base_url() == "https://staging.senso.test/api/v1"


class TestCitationHardRule:
    def test_cited_result_parses(self):
        doc = parse_search_response(
            {
                "results": [
                    {
                        "text": "## Steps\n1. Confirm blast radius...",
                        "title": "Runbook: payments-service p99 latency breach",
                        "id": "cnt_123",
                    }
                ]
            }
        )
        assert doc.content.startswith("## Steps")
        assert doc.citation == "Runbook: payments-service p99 latency breach"
        assert doc.source_id == "cnt_123"

    def test_uncited_content_is_refused(self):
        with pytest.raises(UncitedResponseError):
            parse_search_response({"results": [{"text": "step 3: raise the ceiling"}]})

    def test_source_id_alone_is_a_resolvable_reference(self):
        doc = parse_search_response({"results": [{"content": "body", "content_id": "c9"}]})
        assert doc.source_id == "c9"
        assert doc.citation == "senso:c9"

    def test_single_answer_shape(self):
        doc = parse_search_response({"answer": "raise pool_max to 150", "source": "INC-2417"})
        assert doc.content == "raise pool_max to 150"
        assert doc.citation == "INC-2417"

    def test_empty_results_fail_loudly(self):
        with pytest.raises(NoDocumentFoundError):
            parse_search_response({"results": []})

    def test_unresolvable_shape_fails_loudly(self):
        with pytest.raises(UnexpectedResponseShapeError):
            parse_search_response({"weird": True})

    def test_result_without_content_fails_loudly(self):
        with pytest.raises(UnexpectedResponseShapeError):
            parse_search_response({"results": [{"title": "t", "id": "x"}]})
