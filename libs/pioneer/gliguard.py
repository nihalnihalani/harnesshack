"""GLiGuard client — safety MODERATION of outbound text. Nothing else.

GLiGuard = safety/jailbreak/harm/refusal moderation (the 300M-param 4-task
model, sponsors.md). GLiNER2 = extraction/classification. NEVER swap the two
(CLAUDE.md Learned Rules). This module screens text BEFORE it leaves the
system (Slack, Jira, postmortem) — it does not classify severity.

Real REST client against POST https://api.pioneer.ai/inference (X-API-Key).
Raises NotConfiguredError naming B4 while PIONEER_API_KEY is unset. Never
returns fake data on any path — in particular it NEVER defaults to
"allowed" when the response is unparseable.

CLAIM INTEGRITY: latency_ms is the MEASURED wall-clock of the HTTP call.

ON-SITE CONFIRMATION REQUIRED (B4): exact response-shape field names must be
confirmed against the live API when B4 lands. `parse_screen_response` is
tolerant about container nesting and verdict key spelling
(allowed/safe/flagged) but FAILS LOUDLY (UnexpectedResponseShapeError) when
no explicit verdict is resolvable — an ambiguous moderation response is
treated as an error, never as a pass.
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

logger = logging.getLogger("incidentsherpa.pioneer.gliguard")

PIONEER_INFERENCE_URL = "https://api.pioneer.ai/inference"
MODEL = "gliguard"
_TIMEOUT_SECONDS = 30.0

_RESULT_CONTAINER_KEYS = ("output", "result", "results", "data", "moderation", "predictions")
_CATEGORY_KEYS = ("categories", "violations", "flags", "labels")


@dataclass(frozen=True)
class ScreenResult:
    """GLiGuard moderation verdict with the MEASURED call latency."""

    allowed: bool
    categories: tuple[str, ...]
    latency_ms: float


def _api_key() -> str:
    key = os.environ.get("PIONEER_API_KEY", "").strip()
    if not key:
        raise NotConfiguredError(
            "Pioneer not configured: set PIONEER_API_KEY — see BUILD-STATE.md B4"
        )
    return key


def build_screen_request(text: str) -> dict[str, Any]:
    """Build the GLiGuard moderation inference request body."""
    return {"model": MODEL, "input": text}


def _find_verdict_container(data: Any) -> dict[str, Any]:
    candidates: list[Any] = [data]
    if isinstance(data, dict):
        candidates.extend(data.get(key) for key in _RESULT_CONTAINER_KEYS)
    for candidate in candidates:
        if isinstance(candidate, list) and candidate and isinstance(candidate[0], dict):
            candidate = candidate[0]
        if isinstance(candidate, dict) and (
            "allowed" in candidate or "safe" in candidate or "flagged" in candidate
        ):
            return candidate
    raise UnexpectedResponseShapeError(
        "GLiGuard response has no resolvable verdict (allowed/safe/flagged) — an "
        "ambiguous moderation response is NEVER treated as a pass; confirm the live "
        f"response shape when B4 lands (got: {str(data)[:300]!r})"
    )


def parse_screen_response(data: Any) -> tuple[bool, tuple[str, ...]]:
    """Parse (allowed, categories) from a GLiGuard moderation response.

    Requires an EXPLICIT boolean verdict under one of allowed/safe/flagged
    (flagged is inverted). Categories are optional (empty when absent).
    Unresolvable responses raise UnexpectedResponseShapeError — never a
    default-allow.
    """
    container = _find_verdict_container(data)
    if "allowed" in container:
        verdict, invert = container["allowed"], False
    elif "safe" in container:
        verdict, invert = container["safe"], False
    else:
        verdict, invert = container["flagged"], True
    if not isinstance(verdict, bool):
        raise UnexpectedResponseShapeError(
            f"GLiGuard verdict {verdict!r} is not an explicit boolean — refusing to "
            "guess; confirm the live response shape when B4 lands"
        )
    allowed = (not verdict) if invert else verdict
    categories: tuple[str, ...] = ()
    for key in _CATEGORY_KEYS:
        raw = container.get(key)
        if isinstance(raw, list):
            categories = tuple(str(item) for item in raw)
            break
        if isinstance(raw, dict):  # e.g. {"harm": true, "jailbreak": false}
            categories = tuple(sorted(name for name, hit in raw.items() if hit))
            break
    return allowed, categories


def screen(text: str) -> ScreenResult:
    """Safety-moderate outbound text. Returns the verdict + MEASURED latency.

    Raises NotConfiguredError (B4) keyless, httpx errors on transport/HTTP
    failure (callers wrap in libs.resilience.with_retries), and
    UnexpectedResponseShapeError on an unparseable verdict. Traced via
    Langfuse (loud-warning untraced while B3 is open).
    """
    key = _api_key()
    request_body = build_screen_request(text)

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

    data, latency_ms = call_traced("pioneer.gliguard.screen", _call, logger=logger)
    allowed, categories = parse_screen_response(data)
    return ScreenResult(allowed=allowed, categories=categories, latency_ms=latency_ms)


__all__ = [
    "MODEL",
    "PIONEER_INFERENCE_URL",
    "ScreenResult",
    "build_screen_request",
    "parse_screen_response",
    "screen",
]
