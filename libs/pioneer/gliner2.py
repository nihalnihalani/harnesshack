"""GLiNER2 client — schema-conditioned severity + affected-services extraction.

GLiNER2 = EXTRACTION/CLASSIFICATION. GLiGuard = safety moderation. Never swap
the two (CLAUDE.md Learned Rules — this distinction killed a debate round).

Real REST client against POST https://api.pioneer.ai/inference (X-API-Key,
per sponsors.md / docs.pioneer.ai), schema-conditioned on
{severity: [P0,P1,P2,P3], affected_services: span}. Raises NotConfiguredError
naming B4 while PIONEER_API_KEY is unset. Never returns fake data on any path.

CLAIM INTEGRITY: latency_ms is the MEASURED wall-clock of the HTTP call —
the UI latency badge uses exactly this value, never an estimate.

ON-SITE CONFIRMATION REQUIRED (B4): the exact response-shape field names of
the Pioneer inference API are not publicly documented in full. The request
shape follows the docs.pioneer.ai convention; `parse_extraction_response` is
TOLERANT about where the result container lives but FAILS LOUDLY
(UnexpectedResponseShapeError) on anything it cannot resolve — it never
guesses a severity or invents spans. Confirm field names against the live
API the moment B4 lands and tighten the parser.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

import httpx

from libs.errors import NotConfiguredError, UnexpectedResponseShapeError
from libs.tracing import call_traced

logger = logging.getLogger("incidentsherpa.pioneer.gliner2")

PIONEER_INFERENCE_URL = "https://api.pioneer.ai/inference"
MODEL = "gliner2"
SEVERITY_LABELS = ("P0", "P1", "P2", "P3")
_TIMEOUT_SECONDS = 30.0

# Plausible top-level containers for the inference result. The parser walks
# these in order; it does NOT guess values, only locations.
_RESULT_CONTAINER_KEYS = ("output", "result", "results", "data", "extractions", "predictions")


@dataclass(frozen=True)
class SeverityExtraction:
    """GLiNER2 extraction result with the MEASURED call latency."""

    severity: str  # one of SEVERITY_LABELS
    affected_services: tuple[str, ...]
    latency_ms: float


def _api_key() -> str:
    key = os.environ.get("PIONEER_API_KEY", "").strip()
    if not key:
        raise NotConfiguredError(
            "Pioneer not configured: set PIONEER_API_KEY — see BUILD-STATE.md B4"
        )
    return key


def build_extraction_request(text: str) -> dict[str, Any]:
    """Build the schema-conditioned GLiNER2 inference request body."""
    return {
        "model": MODEL,
        "input": text,
        "schema": {
            "severity": {"type": "classification", "labels": list(SEVERITY_LABELS)},
            "affected_services": {"type": "span"},
        },
    }


def _find_result_container(data: Any) -> dict[str, Any]:
    """Locate the dict that holds `severity` — tolerant on nesting, loud on failure."""
    candidates: list[Any] = [data]
    if isinstance(data, dict):
        candidates.extend(data.get(key) for key in _RESULT_CONTAINER_KEYS)
    for candidate in candidates:
        if isinstance(candidate, list) and candidate and isinstance(candidate[0], dict):
            candidate = candidate[0]
        if isinstance(candidate, dict) and "severity" in candidate:
            return candidate
    raise UnexpectedResponseShapeError(
        "GLiNER2 response has no resolvable 'severity' container — confirm the "
        f"live response shape when B4 lands (got: {str(data)[:300]!r})"
    )


def _coerce_label(value: Any) -> Any:
    """Pull a label out of {label|value|class: ...} / [first] shapes; no guessing."""
    if isinstance(value, list) and value:
        value = value[0]
    if isinstance(value, dict):
        for key in ("label", "value", "class"):
            if key in value:
                return value[key]
    return value


def _coerce_span_text(value: Any) -> Any:
    if isinstance(value, dict):
        for key in ("text", "span", "value"):
            if key in value:
                return value[key]
    return value


def parse_extraction_response(data: Any) -> tuple[str, tuple[str, ...]]:
    """Parse (severity, affected_services) from a GLiNER2 inference response.

    Tolerant about container nesting, strict about values: severity must
    resolve to one of SEVERITY_LABELS and affected_services must be present
    (an empty span list is honest — a MISSING key is an unexpected shape).
    Anything else raises UnexpectedResponseShapeError. Never guesses.
    """
    container = _find_result_container(data)
    severity = _coerce_label(container["severity"])
    if severity not in SEVERITY_LABELS:
        raise UnexpectedResponseShapeError(
            f"GLiNER2 severity {severity!r} is not one of {SEVERITY_LABELS} — "
            "refusing to guess; confirm the live response shape when B4 lands"
        )
    if "affected_services" not in container:
        raise UnexpectedResponseShapeError(
            "GLiNER2 response container has no 'affected_services' key (the schema "
            f"requested it) — got keys {sorted(container)!r}; confirm shape when B4 lands"
        )
    raw_services = container["affected_services"]
    if raw_services is None:
        raw_services = []
    if not isinstance(raw_services, list):
        raw_services = [raw_services]
    services: list[str] = []
    for item in raw_services:
        text = _coerce_span_text(item)
        if not isinstance(text, str):
            raise UnexpectedResponseShapeError(
                f"GLiNER2 affected_services entry {item!r} has no resolvable span text "
                "— confirm the live response shape when B4 lands"
            )
        services.append(text)
    return str(severity), tuple(services)


def extract_severity(text: str) -> SeverityExtraction:
    """Schema-conditioned extraction: severity + affected services + MEASURED latency.

    Raises NotConfiguredError (B4) keyless, httpx errors on transport/HTTP
    failure (callers wrap this in libs.resilience.with_retries), and
    UnexpectedResponseShapeError on an unparseable response. Traced via
    Langfuse (loud-warning untraced while B3 is open).
    """
    key = _api_key()
    request_body = build_extraction_request(text)

    def _call() -> tuple[Any, float]:
        start = time.perf_counter()
        response = httpx.post(
            PIONEER_INFERENCE_URL,
            json=request_body,
            headers={"X-API-Key": key},
            timeout=_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        latency_ms = (time.perf_counter() - start) * 1000.0
        return response.json(), latency_ms

    data, latency_ms = call_traced("pioneer.gliner2.extract_severity", _call, logger=logger)
    severity, services = parse_extraction_response(data)
    return SeverityExtraction(
        severity=severity, affected_services=services, latency_ms=latency_ms
    )


__all__ = [
    "MODEL",
    "PIONEER_INFERENCE_URL",
    "SEVERITY_LABELS",
    "SeverityExtraction",
    "build_extraction_request",
    "extract_severity",
    "parse_extraction_response",
]
