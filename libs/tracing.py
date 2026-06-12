"""Langfuse tracing — import this EVERYWHERE that calls anything (CLAUDE.md).

Real Langfuse init from env. When LANGFUSE_* env vars are empty this raises
NotConfiguredError (BUILD-STATE.md B3) — it does NOT no-op silently. Later
phases rely on that: an untraced call must fail loudly, because "if a call
isn't traced, it doesn't exist to the judges".
"""

from __future__ import annotations

import functools
import os
from collections.abc import Callable
from typing import Any, TypeVar

from libs.errors import NotConfiguredError

_REQUIRED_ENV = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")
_DEFAULT_HOST = "https://cloud.langfuse.com"

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
