"""Langfuse tracing — import this EVERYWHERE that calls anything (CLAUDE.md).

Real Langfuse init from env. When LANGFUSE_* env vars are empty this raises
NotConfiguredError (BUILD-STATE.md B3) — it does NOT no-op silently. Later
phases rely on that: an untraced call must fail loudly, because "if a call
isn't traced, it doesn't exist to the judges".
"""

from __future__ import annotations

import functools
import logging
import os
from collections.abc import Callable
from typing import Any, TypeVar

from libs.errors import NotConfiguredError

_REQUIRED_ENV = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")
_DEFAULT_HOST = "https://cloud.langfuse.com"

# The marker this module puts in its own NotConfiguredError message. @traced
# raises it BEFORE the wrapped callable ever runs, so catching on this marker
# can never swallow a blocker raised from inside the workload itself.
_TRACING_BLOCKER_MARKER = "BUILD-STATE.md B3"

_logger = logging.getLogger("incidentsherpa.tracing")

_client: Any = None

F = TypeVar("F", bound=Callable[..., Any])


def _missing_env() -> list[str]:
    return [key for key in _REQUIRED_ENV if not os.environ.get(key, "").strip()]


def is_configured() -> bool:
    """True when all LANGFUSE_* credentials are present in the environment."""
    return not _missing_env()


def get_langfuse() -> Any:
    """Return the process-wide Langfuse client, initialising it from env.

    Raises NotConfiguredError when LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY
    are empty — see BUILD-STATE.md B3.
    """
    global _client
    missing = _missing_env()
    if missing:
        raise NotConfiguredError(
            f"Langfuse not configured: set {', '.join(missing)} — see BUILD-STATE.md B3"
        )
    if _client is None:
        # Imported lazily so the unconfigured path has zero side effects.
        from langfuse import Langfuse

        _client = Langfuse(
            public_key=os.environ["LANGFUSE_PUBLIC_KEY"].strip(),
            secret_key=os.environ["LANGFUSE_SECRET_KEY"].strip(),
            host=os.environ.get("LANGFUSE_HOST", "").strip() or _DEFAULT_HOST,
        )
    return _client


def traced(name: str) -> Callable[[F], F]:
    """Decorator: run the wrapped callable inside a real Langfuse span.

    Raises NotConfiguredError at CALL time when Langfuse credentials are
    missing — callers in later phases rely on this loud failure; do not
    soften it into a no-op.
    """

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            client = get_langfuse()  # raises NotConfiguredError when blocked (B3)
            with client.start_as_current_span(name=name) as span:
                try:
                    result = fn(*args, **kwargs)
                except Exception as exc:
                    span.update(level="ERROR", status_message=str(exc))
                    raise
                return result

        return wrapper  # type: ignore[return-value]

    return decorator


def call_traced(
    span_name: str,
    fn: Callable[..., Any],
    *args: Any,
    logger: logging.Logger | None = None,
    **kwargs: Any,
) -> Any:
    """Run `fn` inside a real Langfuse span, or untraced with a LOUD warning.

    Library-side counterpart of scripts/tracing_glue.call_traced: while
    Langfuse credentials are missing (BUILD-STATE.md B3) the @traced decorator
    raises NotConfiguredError BEFORE the callable runs; we catch exactly that
    case, warn loudly, and proceed untraced. Tracing never silently no-ops —
    the warning disappears the moment B3 lands. Any other NotConfiguredError
    (raised from inside the workload, e.g. B2/B4/B6) is re-raised untouched.
    """
    log = logger or _logger
    try:
        return traced(span_name)(fn)(*args, **kwargs)
    except NotConfiguredError as exc:
        if _TRACING_BLOCKER_MARKER not in str(exc):
            raise  # a different blocker from inside the workload — never swallowed
        log.warning(
            "=" * 72
            + "\nTRACING DISABLED — Langfuse is not configured (%s).\n"
            "Span %r will NOT appear in any trace. Proceeding UNTRACED.\n"
            "This warning disappears the moment B3 lands (LANGFUSE_* env vars).\n"
            + "=" * 72,
            exc,
            span_name,
        )
        return fn(*args, **kwargs)
