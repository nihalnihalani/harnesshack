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
# Real model id confirmed against the live /inference contract (firing 11,
# 2026-06-13). The authored placeholder "gliner2" / {model,input} shape was
# wrong; the API uses model_id + text + the unified classifications/entities
# schema grammar. See BUILD-STATE.md DECISIONS + CLAUDE.md Learned Rules.
MODEL_ID = "fastino/gliner2-base-v1"
SEVERITY_LABELS = ("P0", "P1", "P2", "P3")
ENTITY_LABEL = "affected_service"
_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class SeverityExtraction:
    """GLiNER2 extraction result.

    `latency_ms` is the SERVER-reported inference time (the model-speed number
    the UI badge cites — distinct from client wall-clock). `confidence` is the
    classifier's own confidence in the severity label.
    """

    severity: str  # one of SEVERITY_LABELS
    affected_services: tuple[str, ...]
    latency_ms: float
    confidence: float = 0.0


def _api_key() -> str:
    key = os.environ.get("PIONEER_API_KEY", "").strip()
    if not key:
        raise NotConfiguredError(
            "Pioneer not configured: set PIONEER_API_KEY — see BUILD-STATE.md B4"
        )
    return key


def build_extraction_request(text: str) -> dict[str, Any]:
    """Build the schema-conditioned GLiNER2 inference request body.

    Confirmed live contract: top-level model_id + text + a unified `schema`
    whose keys must be among {classifications, entities, structures, relations}.
    """
    return {
        "model_id": MODEL_ID,
        "text": text,
        "schema": {
            "classifications": {"severity": list(SEVERITY_LABELS)},
            "entities": [ENTITY_LABEL],
        },
    }


def parse_extraction_response(data: Any) -> tuple[str, tuple[str, ...], float]:
    """Parse (severity, affected_services, confidence) from a GLiNER2 response.

    Real envelope: data.result.data.{severity:{label,confidence},
    entities:{affected_service:[{text,confidence,start,end}]}}. Strict about
    values: severity must resolve to one of SEVERITY_LABELS; never guesses.
    """
    if not isinstance(data, dict):
        raise UnexpectedResponseShapeError(f"GLiNER2 response is not a dict: {str(data)[:200]!r}")
    container = (data.get("result") or {}).get("data")
    if not isinstance(container, dict) or "severity" not in container:
        raise UnexpectedResponseShapeError(
            f"GLiNER2 response has no result.data.severity — got: {str(data)[:300]!r}"
        )
    sev_block = container["severity"]
    severity = sev_block.get("label") if isinstance(sev_block, dict) else sev_block
    confidence = float(sev_block.get("confidence", 0.0)) if isinstance(sev_block, dict) else 0.0
    if severity not in SEVERITY_LABELS:
        raise UnexpectedResponseShapeError(
            f"GLiNER2 severity {severity!r} is not one of {SEVERITY_LABELS} — refusing to guess"
        )
    entities = container.get("entities")
    if not isinstance(entities, dict) or ENTITY_LABEL not in entities:
        got = sorted(entities) if isinstance(entities, dict) else entities
        raise UnexpectedResponseShapeError(
            f"GLiNER2 response has no entities.{ENTITY_LABEL} — got keys {got!r}"
        )
    spans = entities[ENTITY_LABEL] or []
    services: list[str] = []
    for item in spans:
        span_text = item.get("text") if isinstance(item, dict) else item
        if not isinstance(span_text, str):
            raise UnexpectedResponseShapeError(
                f"GLiNER2 entity span {item!r} has no resolvable text — refusing to guess"
            )
        services.append(span_text)
    return str(severity), tuple(services), confidence


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
        wall_ms = (time.perf_counter() - start) * 1000.0
        return response.json(), wall_ms

    data, _wall_ms = call_traced("pioneer.gliner2.extract_severity", _call, logger=logger)
    severity, services, confidence = parse_extraction_response(data)
    # Prefer the SERVER-reported inference latency (model speed, the badge
    # number); fall back to client wall-clock only if absent. Claim integrity.
    server_ms = data.get("latency_ms") if isinstance(data, dict) else None
    latency_ms = float(server_ms) if isinstance(server_ms, (int, float)) else _wall_ms
    return SeverityExtraction(
        severity=severity,
        affected_services=services,
        latency_ms=latency_ms,
        confidence=confidence,
    )


__all__ = [
    "MODEL_ID",
    "PIONEER_INFERENCE_URL",
    "SEVERITY_LABELS",
    "SeverityExtraction",
    "build_extraction_request",
    "extract_severity",
    "parse_extraction_response",
]
