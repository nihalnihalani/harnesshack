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


class TestGliner2RequestShape:
    def test_model_and_input(self):
        body = gliner2.build_extraction_request("payments p99 breach")
        assert body["model"] == "gliner2"
        assert body["input"] == "payments p99 breach"

    def test_schema_conditions_severity_labels(self):
        body = gliner2.build_extraction_request("x")
        assert body["schema"]["severity"] == {
            "type": "classification",
            "labels": ["P0", "P1", "P2", "P3"],
        }

    def test_schema_requests_affected_services_span(self):
        body = gliner2.build_extraction_request("x")
        assert body["schema"]["affected_services"] == {"type": "span"}


class TestGliner2Keyless:
    def test_extract_severity_raises_b4(self):
        with pytest.raises(NotConfiguredError, match="B4"):
            gliner2.extract_severity("payments p99 breach")


class TestGliner2Parse:
    def test_flat_shape(self):
        severity, services = gliner2.parse_extraction_response(
            {"severity": "P0", "affected_services": ["payments-service"]}
        )
        assert severity == "P0"
        assert services == ("payments-service",)

    @pytest.mark.parametrize("container_key", ["output", "result", "results", "data"])
    def test_nested_container_shapes(self, container_key: str):
        data = {container_key: {"severity": "P1", "affected_services": []}}
        assert gliner2.parse_extraction_response(data) == ("P1", ())

    def test_list_container_shape(self):
        data = {"results": [{"severity": "P2", "affected_services": [{"text": "checkout"}]}]}
        assert gliner2.parse_extraction_response(data) == ("P2", ("checkout",))

    def test_label_dict_severity(self):
        data = {"severity": {"label": "P0"}, "affected_services": []}
        assert gliner2.parse_extraction_response(data) == ("P0", ())

    def test_unknown_severity_label_fails_loudly(self):
        with pytest.raises(UnexpectedResponseShapeError):
            gliner2.parse_extraction_response(
                {"severity": "CRITICAL", "affected_services": []}
            )

    def test_missing_severity_fails_loudly(self):
        with pytest.raises(UnexpectedResponseShapeError):
            gliner2.parse_extraction_response({"something": "else"})

    def test_missing_affected_services_key_fails_loudly(self):
        with pytest.raises(UnexpectedResponseShapeError):
            gliner2.parse_extraction_response({"severity": "P0"})

    def test_unresolvable_span_entry_fails_loudly(self):
        with pytest.raises(UnexpectedResponseShapeError):
            gliner2.parse_extraction_response(
                {"severity": "P0", "affected_services": [{"score": 0.9}]}
            )


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
