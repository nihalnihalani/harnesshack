"""Tracing discipline for operational scripts (replay, load generator).

Wraps a callable in libs/tracing.@traced. While Langfuse credentials are
missing (BUILD-STATE.md B3) the decorator raises NotConfiguredError BEFORE the
callable runs; scripts catch exactly that case, emit a LOUD warning, and
proceed untraced. Tracing never silently no-ops — and the moment B3 lands the
warning disappears because @traced starts succeeding.

NotConfiguredError raised by anything else (e.g. ClickHouse B2 inside the
callable) is re-raised untouched: only the tracing layer may be degraded here.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from libs.errors import NotConfiguredError
from libs.tracing import traced

# The marker libs/tracing puts in its NotConfiguredError message. @traced
# raises it before the wrapped callable ever runs, so catching on this marker
# can never swallow a blocker raised from inside the workload itself.
_TRACING_BLOCKER_MARKER = "BUILD-STATE.md B3"


def call_traced[T](
    span_name: str,
    fn: Callable[..., T],
    *args: Any,
    logger: logging.Logger,
    **kwargs: Any,
) -> T:
    """Run `fn` inside a real Langfuse span, or untraced with a loud warning."""
    try:
        return traced(span_name)(fn)(*args, **kwargs)
    except NotConfiguredError as exc:
        if _TRACING_BLOCKER_MARKER not in str(exc):
            raise  # a different blocker (e.g. B2 ClickHouse) — never swallowed
        logger.warning(
            "=" * 72
            + "\nTRACING DISABLED — Langfuse is not configured (%s).\n"
            "Span %r will NOT appear in any trace. Proceeding UNTRACED.\n"
            "This warning disappears the moment B3 lands (LANGFUSE_* env vars).\n"
            + "=" * 72,
            exc,
            span_name,
        )
        return fn(*args, **kwargs)
