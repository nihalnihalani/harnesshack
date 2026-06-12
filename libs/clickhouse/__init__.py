"""ClickHouse Cloud client — typed event log persistence.

Unconfigured behavior is HONEST: with CLICKHOUSE_* env vars empty
(BUILD-STATE.md B2) every call raises NotConfiguredError. No fake writes,
no in-memory pretend store. When credentials land, record_event() performs
a real insert into the `events` table (DDL in libs/clickhouse/schema.py;
table creation/execution is Phase 2).
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from libs.errors import NotConfiguredError

_REQUIRED_ENV = ("CLICKHOUSE_HOST", "CLICKHOUSE_USER", "CLICKHOUSE_PASSWORD")

_client: Any = None


def _missing_env() -> list[str]:
    return [key for key in _REQUIRED_ENV if not os.environ.get(key, "").strip()]


def is_configured() -> bool:
    """True when all CLICKHOUSE_* credentials are present in the environment."""
    return not _missing_env()


def get_client() -> Any:
    """Return a real clickhouse-connect client built from env.

    Raises NotConfiguredError when CLICKHOUSE_* env vars are empty — see
    BUILD-STATE.md B2.
    """
    global _client
    missing = _missing_env()
    if missing:
        raise NotConfiguredError(
            f"ClickHouse not configured: set {', '.join(missing)} — see BUILD-STATE.md B2"
        )
    if _client is None:
        # Imported lazily so the unconfigured path has zero side effects.
        import clickhouse_connect

        _client = clickhouse_connect.get_client(
            host=os.environ["CLICKHOUSE_HOST"].strip(),
            username=os.environ["CLICKHOUSE_USER"].strip(),
            password=os.environ["CLICKHOUSE_PASSWORD"].strip(),
            secure=True,
        )
    return _client


def record_event(
    ts: datetime,
    incident_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    """Persist one typed event into the ClickHouse `events` table.

    The event log IS the product (CLAUDE.md): if it isn't in this table it
    didn't happen. Raises NotConfiguredError while B2 is open — callers
    must surface that, never swallow it.
    """
    client = get_client()  # raises NotConfiguredError while B2 is open
    client.insert(
        "events",
        [[ts, incident_id, event_type, json.dumps(payload, default=str)]],
        column_names=["ts", "incident_id", "event_type", "payload"],
    )
