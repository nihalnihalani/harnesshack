"""scripts/seed_senso.py — document content + honest B6 blocker, no network.

Phase 3 retrieves these documents WITH CITATIONS, so their structure is a
contract: every runbook carries symptom pattern / steps / last applied /
resolution time, and the ownership map carries the suggested-owner framing
the demo cites (dana-chen, 9 of the last 12).
"""

from __future__ import annotations

import pytest

from libs.errors import NotConfiguredError
from scripts.seed_senso import (
    ALL_DOCUMENTS,
    DEFAULT_BASE_URL,
    OWNERSHIP_MAP,
    POSTMORTEMS,
    RUNBOOKS,
    base_url,
    get_api_key,
    main,
)

RUNBOOK_REQUIRED_SECTIONS = (
    "## Symptom pattern",
    "## Steps",
    "## Last applied",
    "## Resolution time",
)


def test_document_inventory_is_3_runbooks_2_postmortems_1_ownership():
    assert len(RUNBOOKS) == 3
    assert len(POSTMORTEMS) == 2
    assert len(ALL_DOCUMENTS) == 6
    titles = [d["title"] for d in ALL_DOCUMENTS]
    assert len(set(titles)) == 6  # unique titles for unambiguous citations


def test_every_document_has_title_summary_text():
    for document in ALL_DOCUMENTS:
        assert set(document.keys()) == {"title", "summary", "text"}
        assert document["title"].strip() and document["summary"].strip()
        assert len(document["text"]) > 400  # substantive, not filler


def test_runbooks_follow_the_required_structure():
    for runbook in RUNBOOKS:
        for section in RUNBOOK_REQUIRED_SECTIONS:
            assert section in runbook["text"], (runbook["title"], section)
        # Numbered, followable steps.
        assert "1." in runbook["text"] and "2." in runbook["text"]


def test_runbooks_cover_the_three_demo_services():
    blob = " ".join(r["title"] + r["text"] for r in RUNBOOKS)
    assert "payments-service" in blob
    assert "payments-db-primary" in blob
    assert "checkout-service" in blob


def test_payments_latency_runbook_step_3_raises_the_pool_ceiling():
    """The demo beat: the agent cites step 3 of this runbook as the mitigation."""
    runbook = next(r for r in RUNBOOKS if "payments-service p99" in r["title"])
    steps = runbook["text"].split("## Steps", 1)[1]
    step_3 = steps.split("\n3.", 1)[1].split("\n4.", 1)[0]  # the full step-3 block
    assert "pool" in step_3.lower() and "ceiling" in step_3.lower()
    assert "100" in step_3 and "150" in step_3


def test_postmortems_reference_real_incident_ids_and_owners():
    blob = " ".join(p["text"] for p in POSTMORTEMS)
    assert "INC-2417" in blob and "INC-2289" in blob
    assert "dana-chen" in blob and "alex-kim" in blob
    # The recorded pattern the causal SQL will rediscover: pool climb precedes impact.
    assert "pool" in blob.lower()


def test_ownership_map_framing_matches_claim_integrity_rules():
    text = OWNERSHIP_MAP["text"]
    assert "dana-chen" in text and "payments-service" in text
    assert "9 of the last 12" in text  # the demo's history framing
    assert "alex-kim" in text and "payments-db-primary" in text
    # CLAUDE.md: "suggests likely owner", never "assigns".
    assert "human always confirms" in text.lower() or "awaiting confirmation" in text.lower()
    assert "auto-assign" not in text.lower().replace("nothing here auto-assigns", "")


def test_get_api_key_raises_not_configured_naming_b6():
    with pytest.raises(NotConfiguredError, match="B6"):
        get_api_key()  # conftest guarantees SENSO_API_KEY is unset


def test_main_exits_nonzero_while_b6_open(capsys):
    assert main([]) == 2
    assert "B6" in capsys.readouterr().err


def test_dry_run_needs_no_credentials(capsys):
    assert main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "3 runbooks, 2 postmortems, 1 ownership" in out


def test_base_url_defaults_to_published_senso_endpoint(monkeypatch):
    monkeypatch.delenv("SENSO_BASE_URL", raising=False)
    assert base_url() == DEFAULT_BASE_URL == "https://sdk.senso.ai/api/v1"
    monkeypatch.setenv("SENSO_BASE_URL", "https://example.test/api/v1")
    assert base_url() == "https://example.test/api/v1"
