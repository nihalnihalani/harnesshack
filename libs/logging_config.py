"""Structured JSON-lines logging — stdlib only (CLAUDE.md: no heavy deps).

One line of JSON per record on stdout: timestamp (UTC ISO-8601), level,
logger, msg, plus any `extra={...}` fields the call site attached. Render
and every log aggregator parse this natively; humans can still read it.

Entrypoints (apps/api/main.py, `python -m apps.worker.agent`, scripts that
log) call configure_logging() once; the call is idempotent so the API app
being imported by tests or by uvicorn workers never stacks handlers.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, datetime

# Attributes every LogRecord carries; anything NOT in this set arrived via
# `extra={...}` at the call site and is emitted as a structured field.
_RESERVED_RECORD_ATTRS = frozenset(
    {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "taskName", "message", "asctime",
    }
)  # fmt: skip


class JSONLinesFormatter(logging.Formatter):
    """Format each record as a single JSON object on one line."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED_RECORD_ATTRS and not key.startswith("_"):
                entry[key] = value
        if record.exc_info and record.exc_info[0] is not None:
            entry["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            entry["stack_info"] = record.stack_info
        # default=str: an unserialisable extra must never kill the log line.
        return json.dumps(entry, default=str)


def configure_logging(level: str | int | None = None) -> None:
    """Install the JSON-lines handler on the root logger (idempotent).

    Level resolution: explicit arg > LOG_LEVEL env var > INFO.
    """
    root = logging.getLogger()
    if level is None:
        level = os.environ.get("LOG_LEVEL", "").strip().upper() or logging.INFO
    root.setLevel(level)
    if any(getattr(h, "_incidentsherpa_json", False) for h in root.handlers):
        return  # already configured — never stack a second JSON handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONLinesFormatter())
    handler._incidentsherpa_json = True  # type: ignore[attr-defined]
    root.addHandler(handler)
