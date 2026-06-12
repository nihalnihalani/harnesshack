"""Pioneer client tests — request-shape construction + tolerant-but-loud parsing.

No credentials, no network: these exercise the REAL request builders and
parsers of libs/pioneer (test isolation of real code). The live HTTP path is
gated behind B4 and exercised via @pytest.mark.live once PIONEER_API_KEY
lands.
"""

from __future__ import annotations

import pytest

from libs.errors import NotConfiguredError, UnexpectedResponseShapeError
from libs.pioneer import gliguard, gliner2

# A REAL response captured from the live Pioneer /inference API (firing 11,
# 2026-06-13) — not a hand-invented fixture. This is the contract the parser
# targets; tests assert against the actual envelope the server returns.
LIVE_RESPONSE = {
    "type": "encoder",
    "inference_id": "8cdc9c0c-7b54-4e31-aa3e-34d621d7c8e7",
    "result": {
        "data": {
            "entities": {
                "affected_service": [
                    {"text": "checkout-service", "confidence": 0.88, "start": 77, "end": 93},
                    {"text": "payments-service", "confidence": 0.77, "start": 0, "end": 16},
                ]
            },
            "severity": {"label": "P3", "confidence": 0.7799},
        }
    },
    "model_id": "fastino/gliner2-base-v1",
    "latency_ms": 199.18,
}


class TestGliner2RequestShape:
    def test_model_id_and_text(self):
        body = gliner2.build_extraction_request("payments p99 breach")
        assert body["model_id"] == "fastino/gliner2-base-v1"
        assert body["text"] == "payments p99 breach"

    def test_schema_uses_unified_grammar(self):
        # keys must be among {classifications, entities, structures, relations}
        body = gliner2.build_extraction_request("x")
        assert body["schema"]["classifications"] == {"severity": ["P0", "P1", "P2", "P3"]}
        assert body["schema"]["entities"] == ["affected_service"]


class TestGliner2Keyless:
    def test_extract_severity_raises_b4(self):
        with pytest.raises(NotConfiguredError, match="B4"):
            gliner2.extract_severity("payments p99 breach")


class TestGliner2Parse:
    def test_live_response_shape(self):
        severity, services, confidence = gliner2.parse_extraction_response(LIVE_RESPONSE)
        assert severity == "P3"
        assert services == ("checkout-service", "payments-service")
        assert confidence == pytest.approx(0.7799, abs=1e-3)

    def test_empty_entity_list_is_honest(self):
        data = {"result": {"data": {"severity": {"label": "P1", "confidence": 0.9},
                                     "entities": {"affected_service": []}}}}
        assert gliner2.parse_extraction_response(data) == ("P1", (), pytest.approx(0.9))

    def test_unknown_severity_label_fails_loudly(self):
        data = {"result": {"data": {"severity": {"label": "CRITICAL"},
                                     "entities": {"affected_service": []}}}}
        with pytest.raises(UnexpectedResponseShapeError):
            gliner2.parse_extraction_response(data)

    def test_missing_severity_fails_loudly(self):
        with pytest.raises(UnexpectedResponseShapeError):
            gliner2.parse_extraction_response({"result": {"data": {"something": "else"}}})

    def test_missing_entities_key_fails_loudly(self):
        data = {"result": {"data": {"severity": {"label": "P0"}}}}
        with pytest.raises(UnexpectedResponseShapeError):
            gliner2.parse_extraction_response(data)

    def test_non_dict_fails_loudly(self):
        with pytest.raises(UnexpectedResponseShapeError):
            gliner2.parse_extraction_response("not a dict")


class TestGliguardRequestShape:
    def test_model_is_gliguard_not_gliner2(self):
        body = gliguard.build_screen_request("update text")
        assert body["model"] == "gliguard"
        assert body["input"] == "update text"
        # Role separation (Learned Rules): the moderation request carries NO
        # extraction schema.
        assert "schema" not in body


class TestGliguardKeyless:
    def test_screen_raises_b4(self):
        with pytest.raises(NotConfiguredError, match="B4"):
            gliguard.screen("outbound text")


class TestGliguardParse:
    def test_allowed_true(self):
        assert gliguard.parse_screen_response({"allowed": True}) == (True, ())

    def test_safe_key(self):
        assert gliguard.parse_screen_response({"safe": False, "categories": ["harm"]}) == (
            False,
            ("harm",),
        )

    def test_flagged_is_inverted(self):
        assert gliguard.parse_screen_response({"flagged": True}) == (False, ())
        assert gliguard.parse_screen_response({"flagged": False}) == (True, ())

    def test_nested_container(self):
        data = {"output": {"allowed": False, "violations": ["jailbreak"]}}
        assert gliguard.parse_screen_response(data) == (False, ("jailbreak",))

    def test_category_dict_shape(self):
        data = {"allowed": False, "categories": {"harm": True, "jailbreak": False}}
        assert gliguard.parse_screen_response(data) == (False, ("harm",))

    def test_no_verdict_fails_loudly_never_default_allow(self):
        with pytest.raises(UnexpectedResponseShapeError):
            gliguard.parse_screen_response({"categories": ["harm"]})

    def test_non_boolean_verdict_fails_loudly(self):
        with pytest.raises(UnexpectedResponseShapeError):
            gliguard.parse_screen_response({"allowed": "yes"})
