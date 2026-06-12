#!/usr/bin/env python3
"""Fire the demo alert at the IncidentSherpa webhook API (POST /trigger).

POSTs demo_assets/incident_payload.json — the payments-service p99_ms 2400 ms
breach alert, whose timestamp and value are the EXACT breach row of the
recorded incident CSV (claim integrity: the alert is the recording, not an
invented number). Prints the response; exits non-zero on any non-200.

Usage:
    python3 scripts/trigger.py [--api-base http://localhost:8000] [--payload PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_PAYLOAD = REPO_ROOT / "demo_assets" / "incident_payload.json"
DEFAULT_API_BASE = "http://localhost:8000"


def load_payload(path: Path) -> dict:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def fire(api_base: str, payload: dict, timeout: float) -> tuple[int, str]:
    """POST the alert; returns (status_code, response_text)."""
    url = f"{api_base.rstrip('/')}/trigger"
    response = httpx.post(url, json=payload, timeout=timeout)
    return response.status_code, response.text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--api-base",
        default=DEFAULT_API_BASE,
        help=f"API base URL, local or Render (default {DEFAULT_API_BASE})",
    )
    parser.add_argument("--payload", type=Path, default=DEFAULT_PAYLOAD, help="alert JSON path")
    parser.add_argument("--timeout", type=float, default=10.0, help="request timeout seconds")
    args = parser.parse_args(argv)

    payload = load_payload(args.payload)
    print(f"POST {args.api_base.rstrip('/')}/trigger <- {args.payload}")
    try:
        status, body = fire(args.api_base, payload, args.timeout)
    except httpx.HTTPError as exc:
        print(f"request failed: {exc}", file=sys.stderr)
        return 1

    print(f"HTTP {status}")
    print(body)
    if status != 200:
        print(
            "non-200 response — while BUILD-STATE.md B2 is open the API answers "
            "503 honestly (alert not persisted)",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
