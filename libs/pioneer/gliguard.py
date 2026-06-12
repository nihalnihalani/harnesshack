"""GLiGuard client — safety MODERATION of outbound text. Nothing else.

GLiGuard = safety/jailbreak/harm/refusal moderation (the 300M-param 4-task
model, sponsors.md). GLiNER2 = extraction/classification. NEVER swap the two
(CLAUDE.md Learned Rules). This module screens text BEFORE it leaves the
system (Slack, Jira, postmortem) — it does not classify severity.

Real REST client against POST https://api.pioneer.ai/inference (X-API-Key).
Raises NotConfiguredError naming B4 while PIONEER_API_KEY is unset. Never
returns fake data on any path — in particular it NEVER defaults to
"allowed" when the response is unparseable.

CONTRACT CONFIRMED LIVE (2026-06-12, keycheck team): the hosted model is
`fastino/gliguard-LLMGuardrails-300M` and uses the SAME unified /inference
grammar as GLiNER2 — `model_id` + `text` + `schema`, where the moderation ask
is a classification task `prompt_safety` with labels ["safe", "unsafe"]
(the API rejects classification tasks with fewer than 2 labels). Response
envelope: result.data.prompt_safety.{label, confidence} plus a top-level
SERVER-reported latency_ms (392ms warm; cold start can take >10s wall —
callers' retry/timeout budgets must tolerate that). The previous
{"model": "gliguard", "input": text} shape 422s and was the pre-firing-11
authored guess that never got the GLiNER2 rewrite.

CLAIM INTEGRITY: latency_ms prefers the SERVER-reported inference time (the
model-speed number a badge may cite); client wall-clock only as fallback.
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
MODEL_ID = "fastino/gliguard-LLMGuardrails-300M"
SAFETY_TASK = "prompt_safety"
SAFETY_LABELS = ("safe", "unsafe")
# Cold starts measured >10s wall (server latency_ms itself stays ~400ms);
# the generous timeout is deliberate — a slow screen beats an unscreened send.
_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class ScreenResult:
    """GLiGuard moderation verdict with the MEASURED latency.

    `confidence` is the classifier's confidence in its label (0.0 when the
    caller constructed the result without one, e.g. in tests).
    """

    allowed: bool
    categories: tuple[str, ...]
    latency_ms: float
    confidence: float = 0.0


def _api_key() -> str:
    key = os.environ.get("PIONEER_API_KEY", "").strip()
    if not key:
        raise NotConfiguredError(
            "Pioneer not configured: set PIONEER_API_KEY — see BUILD-STATE.md B4"
        )
    return key


def build_screen_request(text: str) -> dict[str, Any]:
    """Build the GLiGuard moderation inference request body.

    Confirmed live contract: model_id + text + a unified `schema` whose
    moderation ask is the prompt_safety classification with BOTH labels
    (the API requires >=2 labels per classification task). Role separation
    (Learned Rules): no entity extraction in a moderation request.
    """
    return {
        "model_id": MODEL_ID,
        "text": text,
        "schema": {"classifications": {SAFETY_TASK: list(SAFETY_LABELS)}},
    }


def parse_screen_response(data: Any) -> tuple[bool, tuple[str, ...], float]:
    """Parse (allowed, categories, confidence) from a GLiGuard response.

    Real envelope: data.result.data.prompt_safety.{label, confidence}.
    Strict: the label must be exactly "safe" or "unsafe" — anything else
    raises UnexpectedResponseShapeError. An unresolvable response is NEVER
    treated as a pass.
    """
    if not isinstance(data, dict):
        raise UnexpectedResponseShapeError(
            f"GLiGuard response is not a dict: {str(data)[:200]!r}"
        )
    container = (data.get("result") or {}).get("data")
    if not isinstance(container, dict) or SAFETY_TASK not in container:
        raise UnexpectedResponseShapeError(
            f"GLiGuard response has no result.data.{SAFETY_TASK} — an ambiguous "
            f"moderation response is NEVER a pass (got: {str(data)[:300]!r})"
        )
    verdict_block = container[SAFETY_TASK]
    label = verdict_block.get("label") if isinstance(verdict_block, dict) else verdict_block
    if label not in SAFETY_LABELS:
        raise UnexpectedResponseShapeError(
            f"GLiGuard label {label!r} is not one of {SAFETY_LABELS} — refusing to guess"
        )
    confidence = (
        float(verdict_block.get("confidence", 0.0))
        if isinstance(verdict_block, dict)
        else 0.0
    )
    allowed = label == "safe"
    categories: tuple[str, ...] = () if allowed else (SAFETY_TASK,)
    return allowed, categories, confidence


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
        wall_ms = (time.perf_counter() - start) * 1000.0
        return response.json(), wall_ms

    data, wall_ms = call_traced("pioneer.gliguard.screen", _call, logger=logger)
    allowed, categories, confidence = parse_screen_response(data)
    # Prefer the SERVER-reported inference latency; wall-clock as fallback.
    server_ms = data.get("latency_ms") if isinstance(data, dict) else None
    latency_ms = float(server_ms) if isinstance(server_ms, (int, float)) else wall_ms
    return ScreenResult(
        allowed=allowed,
        categories=categories,
        latency_ms=latency_ms,
        confidence=confidence,
    )


__all__ = [
    "MODEL_ID",
    "PIONEER_INFERENCE_URL",
    "SAFETY_LABELS",
    "SAFETY_TASK",
    "ScreenResult",
    "build_screen_request",
    "parse_screen_response",
    "screen",
]
