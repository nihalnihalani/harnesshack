#!/usr/bin/env python3
"""Seed the Senso.ai knowledge base — runbooks, postmortems, ownership map.

Authors-in-code and uploads via the VERIFIED-LIVE Senso apiv2 REST API
(https://apiv2.senso.ai/api/v1, X-API-Key auth — keys are `tgr_`-prefixed):
3 service runbooks, 2 past postmortem summaries, and the service ownership
map. Phase 3 retrieves these WITH CITATIONS during a live incident — the
content is therefore structured (symptom pattern / steps / last applied /
resolution time), not filler.

Raises NotConfiguredError naming B6 while SENSO_API_KEY is unset
(BUILD-STATE.md). No offline pretend mode — a hallucinated runbook is worse
than no runbook.

Ingestion is the VERIFIED-LIVE two-step S3 presigned upload:
  (1) POST /org/kb/upload with file metadata (filename, size, content_type,
      md5) -> {results:[{content_id, upload_url, status:"upload_pending"}]}
  (2) PUT the raw bytes to the returned presigned upload_url.
Senso dedupes by content_hash_md5, so re-seeding the same bytes is safe.

Usage:
    python3 scripts/seed_senso.py [--dry-run] [--verify]
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from libs.errors import NotConfiguredError

DEFAULT_BASE_URL = "https://apiv2.senso.ai/api/v1"
UPLOAD_PATH = "/org/kb/upload"  # POST file metadata -> presigned PUT url
SEARCH_PATH = "/org/search"  # POST {query, max_results} -> grounded answer + results
_CONTENT_TYPE = "text/markdown"
_NO_MATCH_ANSWER = "No results found for your query."

# --verify polling budget: ingestion+indexing completes within ~10s; we allow
# generous headroom so the verify gate is robust, not flaky.
_VERIFY_TIMEOUT_SECONDS = 90.0
_VERIFY_POLL_INTERVAL_SECONDS = 5.0

# ---------------------------------------------------------------------------
# Knowledge-base content (authored in code — single reviewable source)
# ---------------------------------------------------------------------------

RUNBOOKS: list[dict[str, str]] = [
    {
        "title": "Runbook: payments-service p99 latency breach",
        "summary": "Diagnose and mitigate payments-service p99_ms above the 2400ms SLO.",
        "text": """# Runbook: payments-service p99 latency breach

## Symptom pattern
- payments-service p99_ms climbs past the 2400ms SLO threshold; p50 often stays near
  baseline (~180ms) until late in the incident.
- Checkout conversion alerts usually follow within 1-2 minutes (checkout-service calls
  payments-service synchronously).
- In both prior occurrences the latency rise was PRECEDED by payments-db-primary
  connection pool saturation (pool_used trending toward pool_max=100) by 3-5 minutes.

## Steps
1. Confirm blast radius: compare payments-service p99_ms against checkout-service
   p99_ms; if checkout is also degrading, declare P0 and page the payments on-call.
2. Check payments-db-primary pool metrics (pool_used vs pool_max). If pool_used is at
   or near 100, this is pool exhaustion — continue; otherwise jump to step 5.
3. Raise the payments-db-primary connection pool ceiling: increase pool_max from 100
   to 150 in db-config/payments-primary.yaml and roll the connection proxy. This is
   the mitigation that resolved INC-2417; latency recovery began within ~4 minutes.
4. Identify the connection consumer: query pg_stat_activity for idle-in-transaction
   sessions grouped by application_name; kill sessions older than 10 minutes.
5. If the pool is healthy, check the payments-service deploy log for releases in the
   last hour and roll back the most recent canary.
6. Verify recovery: p99_ms back under 400ms for 10 consecutive minutes before
   declaring mitigated.

## Last applied
2026-04-18, INC-2417 (steps 2-3-4, in that order).

## Resolution time
22 minutes (INC-2417). Historical median for this pattern: 25 minutes.
""",
    },
    {
        "title": "Runbook: payments-db-primary connection pool exhaustion",
        "summary": "Recover payments-db-primary when pool_used reaches pool_max (100).",
        "text": """# Runbook: payments-db-primary connection pool exhaustion

## Symptom pattern
- pool_used departs its ~40-connection baseline and climbs steadily toward
  pool_max=100 over several minutes; once pinned at 100, new connection attempts
  queue and downstream service latency (payments-service first) rises sharply.
- Typical climb-to-impact lead time observed historically: 3-5 minutes — treat any
  sustained climb past 60 as an early warning, not noise.

## Steps
1. Confirm exhaustion is real: pool_used == pool_max for more than 30s, plus
   connection-wait queue depth > 0 on the proxy.
2. Find the consumer: pg_stat_activity grouped by application_name and state;
   the usual suspects are idle-in-transaction sessions from batch jobs
   (settlement-batch has caused this twice).
3. Apply the short-term relief valve: raise pool_max 100 -> 150 in
   db-config/payments-primary.yaml and roll the connection proxy (no primary
   restart required).
4. Kill leaked sessions: terminate idle-in-transaction sessions older than 10
   minutes; re-check pool_used drops below 80.
5. If a batch job is the consumer, pause its scheduler entry and file a follow-up
   to move it to the read replica.
6. Verify: pool_used stable under 60 for 15 minutes; downstream p99 recovered.

## Last applied
2026-03-02, INC-2289 (steps 2-4-5; ceiling raise was NOT needed once the batch
job was paused).

## Resolution time
31 minutes (INC-2289). The ceiling raise alone (step 3) restores headroom in
under 5 minutes when applied early.
""",
    },
    {
        "title": "Runbook: checkout-service degradation",
        "summary": "Triage checkout-service p99_ms degradation (usually downstream).",
        "text": """# Runbook: checkout-service degradation

## Symptom pattern
- checkout-service p99_ms rises from its ~150ms baseline toward 400ms+; checkout
  conversion dips follow within minutes.
- In most recorded cases checkout is the DOWNSTREAM victim: its synchronous call to
  payments-service inherits payments latency. A checkout-only degradation (payments
  healthy) is the rarer, genuinely-local case.

## Steps
1. Compare timelines first: if payments-service p99_ms degraded BEFORE
   checkout-service, do not page checkout owners — follow the payments-service
   latency runbook and post a status note tagging checkout as downstream impact.
2. If payments is healthy, check checkout-service cache hit rate (Redis); below 70%
   indicates a cache stampede — enable the request-coalescing flag.
3. Check the checkout deploy log; roll back any release in the last hour.
4. Shed load if conversion is dropping: enable the static checkout fallback page for
   anonymous traffic.
5. Verify: p99_ms under 250ms and conversion back to baseline for 10 minutes.

## Last applied
2026-04-18, INC-2417 (step 1 — confirmed downstream of payments; no local action).

## Resolution time
18 minutes (tracked INC-2417's payments mitigation; no checkout-local work needed).
""",
    },
]

POSTMORTEMS: list[dict[str, str]] = [
    {
        "title": "Postmortem summary: INC-2417 — payments p99 breach via DB pool exhaustion",
        "summary": "2026-04-18 P0: pool exhaustion on payments-db-primary drove payments "
        "p99 past SLO; resolved by raising the pool ceiling.",
        "text": """# Postmortem summary: INC-2417 (2026-04-18)

## What happened
A slow climb in payments-db-primary pool_used (baseline ~40 of pool_max 100) began
at 09:41 UTC, driven by idle-in-transaction sessions leaked by a misconfigured
retry loop in the settlement worker. The pool reached exhaustion at 09:45;
payments-service p99_ms breached the 2400ms SLO at 09:45:30 — roughly four minutes
after the climb began. checkout-service degraded downstream one minute later.

## Resolution
On-call (dana-chen) followed the payments latency runbook: confirmed pool
saturation (step 2), raised pool_max 100 -> 150 (step 3), then killed leaked
sessions (step 4). p99 recovery began ~4 minutes after the ceiling raise; full
recovery in 22 minutes end-to-end.

## Root cause
Settlement worker retry loop opened a new transaction per retry without closing
the previous session. Fix shipped 2026-04-21 (bounded retries + session reuse).

## Lessons
- The pool climb was visible minutes before customer impact; alerting on
  pool_used > 60 sustained would have bought ~4 minutes of lead time.
- The ceiling raise is a safe, fast relief valve — apply it BEFORE deep diagnosis
  when exhaustion is confirmed.
""",
    },
    {
        "title": "Postmortem summary: INC-2289 — payments-db-primary pool exhaustion "
        "during batch settlement",
        "summary": "2026-03-02 P1: nightly settlement batch saturated the primary's "
        "connection pool; resolved by pausing the batch and killing leaked sessions.",
        "text": """# Postmortem summary: INC-2289 (2026-03-02)

## What happened
The nightly settlement batch was rescheduled into the early-morning traffic ramp.
Its connection fan-out pushed payments-db-primary pool_used from ~40 to 100 over
six minutes starting 06:12 UTC. payments-service p99_ms degraded to ~1900ms (no
SLO breach, P1) before mitigation.

## Resolution
On-call (alex-kim) followed the pool exhaustion runbook: identified
settlement-batch as the consumer via pg_stat_activity (step 2), killed
idle-in-transaction sessions (step 4), and paused the batch scheduler entry
(step 5). Pool headroom recovered without a ceiling raise. 31 minutes end-to-end.

## Root cause
Batch schedule change reviewed without a capacity check against the morning
traffic ramp; the batch also held transactions open across network calls.

## Lessons
- Batch workloads belong on the read replica; migration ticket PAY-1872.
- pool_used climbs with a LINEAR shape and ~1 connection/5s slope are the
  batch-fan-out signature — distinguishable from leak-driven climbs (INC-2417),
  which accelerate.
""",
    },
]

OWNERSHIP_MAP: dict[str, str] = {
    "title": "Service ownership map: payments and checkout surfaces",
    "summary": "Who owns and most often resolves incidents for payments-service, "
    "payments-db-primary, and checkout-service.",
    "text": """# Service ownership map

Suggested-owner data for incident routing. The agent SUGGESTS a likely owner from
this history — a human always confirms; nothing here auto-assigns.

## payments-service
- Primary owner: dana-chen (payments platform team)
- History: resolved 9 of the last 12 payments-service incidents (Jan-May 2026),
  including INC-2417. Deepest context on the payments<->payments-db-primary
  connection path.
- Secondary: miguel-santos (payments platform, on-call rotation B).

## payments-db-primary
- Primary owner: alex-kim (database reliability team)
- History: led resolution of INC-2289 and owns the connection-proxy/pool
  configuration (db-config/payments-primary.yaml); reviewer of record for pool
  ceiling changes.
- Secondary: dana-chen (for pool-driven payments impact).

## checkout-service
- Primary owner: priya-raman (storefront team)
- History: resolved 5 of the last 7 checkout-service incidents; for downstream
  degradations (payments-rooted), defers to dana-chen per runbook step 1.
- Secondary: jordan-lee (storefront, on-call rotation B).
""",
}

ALL_DOCUMENTS: list[dict[str, str]] = [*RUNBOOKS, *POSTMORTEMS, OWNERSHIP_MAP]


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


def get_api_key() -> str:
    """SENSO_API_KEY from env — raises NotConfiguredError naming B6 if absent."""
    key = os.environ.get("SENSO_API_KEY", "").strip()
    if not key:
        raise NotConfiguredError(
            "Senso not configured: set SENSO_API_KEY — see BUILD-STATE.md B6"
        )
    return key


def base_url() -> str:
    return os.environ.get("SENSO_BASE_URL", "").strip() or DEFAULT_BASE_URL


def _slugify(title: str) -> str:
    """Stable filename slug from a document title (e.g. 'payments-p99-...md')."""
    keep = [c.lower() if c.isalnum() else "-" for c in title]
    slug = "".join(keep)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")[:80] or "document"


def document_bytes(document: dict[str, str]) -> bytes:
    """Render one authored document to the markdown bytes Senso ingests.

    The title heads the file and the summary precedes the body so retrieval's
    grounded answer has both the citable title and a one-line gist.
    """
    body = f"# {document['title']}\n\n> {document['summary']}\n\n{document['text']}"
    return body.encode("utf-8")


def upload_document(client: httpx.Client, document: dict[str, str]) -> dict:
    """Two-step VERIFIED-LIVE ingest of one document; returns the upload result.

    (1) POST /org/kb/upload with the file metadata (md5 lets Senso dedupe).
    (2) PUT the raw bytes to the returned presigned upload_url.
    Treats HTTP 200 + status "upload_pending" as success. Raises on any non-2xx
    or a missing upload_url — no silent partial uploads.
    """
    data = document_bytes(document)
    filename = f"{_slugify(document['title'])}.md"
    md5_hex = hashlib.md5(data).hexdigest()

    meta_resp = client.post(
        UPLOAD_PATH,
        json={
            "files": [
                {
                    "filename": filename,
                    "file_size_bytes": len(data),
                    "content_type": _CONTENT_TYPE,
                    "content_hash_md5": md5_hex,
                }
            ]
        },
    )
    if meta_resp.status_code >= 300:
        raise RuntimeError(
            f"Senso /org/kb/upload failed for {filename!r}: "
            f"HTTP {meta_resp.status_code} {meta_resp.text[:500]}"
        )
    meta = meta_resp.json()
    results = meta.get("results") or []
    if not results:
        raise RuntimeError(
            f"Senso /org/kb/upload returned no results for {filename!r}: {meta!r}"
        )
    entry = results[0]
    upload_url = entry.get("upload_url")
    if not upload_url:
        raise RuntimeError(
            f"Senso /org/kb/upload returned no upload_url for {filename!r}: {entry!r}"
        )

    # Step 2: presigned PUT of the raw bytes. The presigned URL is absolute and
    # carries its own auth — do NOT send the X-API-Key header here.
    put_resp = httpx.put(
        upload_url,
        content=data,
        headers={"Content-Type": _CONTENT_TYPE},
        timeout=60.0,
    )
    if put_resp.status_code != 200:
        raise RuntimeError(
            f"Senso presigned PUT failed for {filename!r}: "
            f"HTTP {put_resp.status_code} {put_resp.text[:300]}"
        )

    return {
        "filename": filename,
        "content_id": entry.get("content_id"),
        "ingestion_run_id": entry.get("ingestion_run_id"),
        "status": entry.get("status"),
    }


def seed(api_key: str) -> list[dict]:
    """Upload every document; returns the per-document upload results."""
    uploaded: list[dict] = []
    with httpx.Client(
        base_url=base_url(),
        headers={"X-API-Key": api_key},
        timeout=30.0,
    ) as client:
        for document in ALL_DOCUMENTS:
            result = upload_document(client, document)
            uploaded.append(result)
            print(
                f"uploaded: {document['title']!r} -> "
                f"content_id={result['content_id']} status={result['status']}"
            )
    return uploaded


# ---------------------------------------------------------------------------
# Verify — poll search until each runbook topic is grounded
# ---------------------------------------------------------------------------

VERIFY_QUERIES: list[str] = [
    "payments-service p99 latency breach",
    "payments-db-primary connection pool exhaustion",
    "checkout-service degradation",
]


def _search(client: httpx.Client, query: str) -> dict:
    resp = client.post(SEARCH_PATH, json={"query": query, "max_results": 3})
    resp.raise_for_status()
    return resp.json()


def verify(api_key: str) -> bool:
    """Poll POST /org/search for each runbook topic until grounded (or time out).

    Returns True only if every topic returns total_results>0 within the budget.
    Prints the grounded answer + top citation for each.
    """
    all_ok = True
    with httpx.Client(
        base_url=base_url(),
        headers={"X-API-Key": api_key},
        timeout=60.0,
    ) as client:
        for query in VERIFY_QUERIES:
            deadline = time.monotonic() + _VERIFY_TIMEOUT_SECONDS
            grounded: dict | None = None
            while time.monotonic() < deadline:
                data = _search(client, query)
                if data.get("total_results", 0) > 0 and data.get("results"):
                    if data.get("answer") != _NO_MATCH_ANSWER:
                        grounded = data
                        break
                time.sleep(_VERIFY_POLL_INTERVAL_SECONDS)

            if grounded is None:
                all_ok = False
                print(f"VERIFY FAIL: {query!r} — no grounded result within "
                      f"{_VERIFY_TIMEOUT_SECONDS:.0f}s", file=sys.stderr)
                continue

            top = grounded["results"][0]
            citation = f"{top.get('title')} ({top.get('content_id')})"
            answer = grounded["answer"]
            print(f"\nVERIFY OK: {query!r}")
            print(f"  citation: {citation}")
            print(f"  answer: {answer[:400]}")
    return all_ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the authored documents without uploading (no credentials needed)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="after seeding, poll /org/search per runbook topic until grounded",
    )
    args = parser.parse_args(argv)

    if args.dry_run:
        for document in ALL_DOCUMENTS:
            print(f"--- {document['title']} ({len(document['text'])} chars)")
        print(f"{len(ALL_DOCUMENTS)} documents authored (3 runbooks, 2 postmortems, 1 ownership)")
        return 0

    try:
        api_key = get_api_key()
    except NotConfiguredError as exc:
        print(f"blocked: {exc}", file=sys.stderr)
        return 2

    uploaded = seed(api_key)
    print(f"seeded {len(uploaded)} documents into Senso ({base_url()})")

    if args.verify:
        print("\nverifying (polling /org/search per runbook topic)...")
        if not verify(api_key):
            print("verify: NOT all topics grounded", file=sys.stderr)
            return 1
        print("\nverify: all runbook topics return grounded answers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
