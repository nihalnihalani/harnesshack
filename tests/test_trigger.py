"""scripts/trigger.py + demo_assets/incident_payload.json — credential-free.

The payload is validated through the API's REAL pydantic model and the REAL
FastAPI app (in-process TestClient — actual request handling, no mocked
endpoint). Claim integrity: the alert's timestamp/value must be the exact
breach row of the recorded CSV.
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import AlertPayload, app
from scripts import incident_profile as profile
from scripts.trigger import DEFAULT_PAYLOAD, load_payload

REPO = Path(__file__).resolve().parents[1]
CSV_PATH = REPO / "demo_assets" / "incident_metrics.csv"


def test_payload_is_wellformed_and_validates_against_the_real_api_model():
    payload = load_payload(DEFAULT_PAYLOAD)
    alert = AlertPayload.model_validate(payload)  # the API's actual 422 gate
    assert alert.service == profile.PAYMENTS
    assert alert.metric == profile.P99
    assert alert.value >= profile.BREACH_THRESHOLD_MS
    assert alert.incident_id  # explicit incident_id field, per demo script
    assert alert.timestamp.tzinfo is not None  # ISO8601 with timezone


def test_payload_matches_the_recorded_breach_row_exactly():
    """The alert IS the recording — timestamp and value come from the CSV."""
    payload = load_payload(DEFAULT_PAYLOAD)
    breach_ts = datetime.fromisoformat(payload["timestamp"].replace("Z", "+00:00"))

    with CSV_PATH.open(newline="") as fh:
        breach_row = next(
            r
            for r in csv.DictReader(fh)
            if r["service"] == profile.PAYMENTS
            and r["metric_name"] == profile.P99
            and float(r["value"]) >= profile.BREACH_THRESHOLD_MS
        )

    csv_ts = datetime.strptime(breach_row["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    assert breach_ts == csv_ts
    assert payload["value"] == float(breach_row["value"])
    # And the breach row sits exactly 250 s after the pool climb onset.
    offset = (csv_ts - profile.WINDOW_START).total_seconds()
    assert offset == profile.PAYMENTS_BREACH_OFFSET


def test_trigger_against_real_app_gets_honest_503_while_b2_open():
    """In-process POST to the real app: valid alert, honest 503 (not fake 200)."""
    payload = load_payload(DEFAULT_PAYLOAD)
    client = TestClient(app)
    response = client.post("/trigger", json=payload)
    assert response.status_code == 503
    assert "B2" in response.json()["detail"]


def test_trigger_rejects_malformed_alert_shape():
    client = TestClient(app)
    response = client.post("/trigger", json={"service": "payments-service"})
    assert response.status_code == 422
