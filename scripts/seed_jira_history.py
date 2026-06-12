#!/usr/bin/env python3
"""Seed the demo Jira site with the 90-day incident history (Phase 5 / B5).

Creates the PLAT (Platform) project and 16 issues whose content EXACTLY backs
the Senso ownership map (scripts/seed_senso.py): 12 payments-service incidents
of which 9 were resolved by dana-chen and 3 by miguel-santos, the INC-2417 and
INC-2289 postmortem mirrors, priya-raman's checkout incident, and the
still-open "pool_used > 60 alert" follow-up from INC-2417 — the unfinished
ticket the Airbyte Context Store should surface during the live incident.

Resolved-by attribution lives in the issue DESCRIPTION text (dana-chen et al.
are not Jira users on this fresh site); that text is what the Airbyte semantic
query reads. Issue created-dates are today — Jira Cloud does not allow
backdating — the dates in summaries/descriptions carry the timeline.

All writes go through the already-authorized Composio Jira connection
(B7 ACTIVE), the same surface the live agent uses.

Usage:
    python3 scripts/seed_jira_history.py [--dry-run]
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile

PROJECT_KEY = "PLAT"
PROJECT_NAME = "Platform"

# Company-managed Kanban — the template REST v3 can create.
PROJECT_TEMPLATES = [
    "com.pyxis.greenhopper.jira:gh-simplified-kanban-classic",
    "com.pyxis.greenhopper.jira:gh-simplified-agility-kanban",
    "com.pyxis.greenhopper.jira:gh-kanban-template",
]

RESOLVED = "Done"
OPEN = "To Do"


def _issue(summary: str, description: str, labels: list[str], status: str) -> dict:
    return {
        "summary": summary,
        "description": description,
        "labels": labels,
        "status": status,
    }


# ---------------------------------------------------------------------------
# The 12 payments-service incidents (Jan-May 2026): 9 dana-chen, 3 miguel-santos
# — the literal source of "resolved 9 of the last 12 payments-service
# incidents" in the Senso ownership map. Order: newest first.
# ---------------------------------------------------------------------------

ISSUES: list[dict] = [
    _issue(
        "P1 2026-05-22: payments-service p99 latency regression after canary deploy v2.41.0",
        "Severity: P1. Date: 2026-05-22. Services: payments-service.\n\n"
        "Symptom: p99_ms rose from ~180ms baseline to 1400ms within 10 minutes of the "
        "v2.41.0 canary reaching 25% traffic. No DB involvement (pool_used flat at ~40).\n\n"
        "Resolution: canary rolled back per payments latency runbook step 5; latency "
        "recovered in 6 minutes. Root cause: unbounded response-validation middleware "
        "added in v2.41.0. Fix shipped in v2.41.1.\n\n"
        "Resolved by: dana-chen (payments platform). Duration: 19 minutes.",
        ["incident", "payments-service", "P1"],
        RESOLVED,
    ),
    _issue(
        "P2 2026-05-09: payments-service elevated 5xx on card-auth path",
        "Severity: P2. Date: 2026-05-09. Services: payments-service.\n\n"
        "Symptom: 5xx rate on POST /card-auth climbed to 2.1% (baseline <0.1%) after an "
        "upstream provider began returning a new error shape.\n\n"
        "Resolution: response parser hardened to tolerate the new shape; retries with "
        "jitter added for the provider's 503s.\n\n"
        "Resolved by: dana-chen (payments platform). Duration: 41 minutes.",
        ["incident", "payments-service", "P2"],
        RESOLVED,
    ),
    _issue(
        "P1 2026-05-02: payments-service webhook retry storm after provider outage",
        "Severity: P1. Date: 2026-05-02. Services: payments-service.\n\n"
        "Symptom: provider outage caused 40k queued webhooks; on recovery the redelivery "
        "burst saturated payments-service workers and p99 breached 2000ms.\n\n"
        "Resolution: redelivery concurrency capped at the ingress proxy; backlog drained "
        "over 25 minutes. Follow-up: token-bucket rate limit on webhook ingest (shipped "
        "2026-05-06).\n\n"
        "Resolved by: dana-chen (payments platform). Duration: 33 minutes.",
        ["incident", "payments-service", "P1"],
        RESOLVED,
    ),
    _issue(
        "P2 2026-04-27: payments-service memory creep — restart mitigation and leak fix",
        "Severity: P2. Date: 2026-04-27. Services: payments-service.\n\n"
        "Symptom: RSS grew ~80MB/day per pod; weekly OOM restarts began impacting tail "
        "latency during restart windows.\n\n"
        "Resolution: leak traced to an unbounded per-merchant feature-flag cache; LRU "
        "bound applied. Interim fortnightly restart cron removed after the fix soaked.\n\n"
        "Resolved by: dana-chen (payments platform). Duration: 2 days (non-paging).",
        ["incident", "payments-service", "P2"],
        RESOLVED,
    ),
    # --- INC-2417: the postmortem mirror (Senso: seed_senso.py POSTMORTEMS[0]) ---
    _issue(
        "[INC-2417] P0 2026-04-18: payments-service p99 SLO breach — payments-db-primary "
        "connection pool exhaustion",
        "Severity: P0. Date: 2026-04-18. Services: payments-service, payments-db-primary, "
        "checkout-service (downstream).\n\n"
        "Symptom: payments-db-primary pool_used climbed from ~40 baseline starting 09:41 UTC "
        "(leaked idle-in-transaction sessions from the settlement worker retry loop); pool "
        "exhausted (100/100) at 09:45; payments-service p99_ms breached the 2400ms SLO at "
        "09:45:30 — about four minutes after the climb began. checkout-service degraded "
        "downstream one minute later.\n\n"
        "Resolution: payments latency runbook steps 2-3-4 — confirmed pool saturation, raised "
        "pool_max 100 -> 150 in db-config/payments-primary.yaml, killed leaked sessions. p99 "
        "recovery began ~4 minutes after the ceiling raise.\n\n"
        "Root cause: settlement worker retry loop opened a new transaction per retry without "
        "closing the previous session. Fix shipped 2026-04-21.\n\n"
        "Resolved by: dana-chen (payments platform). Duration: 22 minutes. "
        "Postmortem: INC-2417 (in Senso).",
        ["incident", "payments-service", "payments-db-primary", "P0", "postmortem"],
        RESOLVED,
    ),
    _issue(
        "P2 2026-04-04: payments-service refunds queue drain stalled",
        "Severity: P2. Date: 2026-04-04. Services: payments-service.\n\n"
        "Symptom: refunds queue depth grew monotonically for 3 hours; consumer group stuck "
        "on a poison message with a malformed currency code.\n\n"
        "Resolution: poison message dead-lettered; schema validation added at enqueue time.\n\n"
        "Resolved by: miguel-santos (payments platform, rotation B). Duration: 55 minutes.",
        ["incident", "payments-service", "P2"],
        RESOLVED,
    ),
    _issue(
        "P1 2026-03-21: payments-service timeout spike during morning traffic ramp",
        "Severity: P1. Date: 2026-03-21. Services: payments-service.\n\n"
        "Symptom: client-side timeouts spiked to 3% during the 06:00-07:00 UTC ramp; "
        "autoscaler was scaling on CPU while the bottleneck was connection establishment.\n\n"
        "Resolution: autoscaler target switched to in-flight requests; pre-scale schedule "
        "added for the morning ramp.\n\n"
        "Resolved by: dana-chen (payments platform). Duration: 38 minutes.",
        ["incident", "payments-service", "P1"],
        RESOLVED,
    ),
    _issue(
        "P2 2026-03-14: payments-service stale currency-rate cache served for 40 minutes",
        "Severity: P2. Date: 2026-03-14. Services: payments-service.\n\n"
        "Symptom: rate-refresh job failed silently after an upstream TLS cert rotation; "
        "conversions used rates up to 40 minutes stale.\n\n"
        "Resolution: refresh job alerting added (staleness > 5 min pages); cert pinning "
        "removed in favor of system trust store.\n\n"
        "Resolved by: miguel-santos (payments platform, rotation B). Duration: 64 minutes.",
        ["incident", "payments-service", "P2"],
        RESOLVED,
    ),
    _issue(
        "P1 2026-03-07: payments-service connection errors during db failover drill",
        "Severity: P1. Date: 2026-03-07. Services: payments-service, payments-db-primary.\n\n"
        "Symptom: planned payments-db-primary failover drill; payments-service connection "
        "pool did not re-resolve the new primary for 90 seconds (DNS TTL pinning), causing "
        "a burst of 5xx.\n\n"
        "Resolution: driver upgraded to honor topology-change notices; drill re-run clean "
        "on 2026-03-12.\n\n"
        "Resolved by: dana-chen (payments platform). Duration: 12 minutes.",
        ["incident", "payments-service", "P1"],
        RESOLVED,
    ),
    _issue(
        "P2 2026-02-20: payments-service idempotency-key collisions on client retries",
        "Severity: P2. Date: 2026-02-20. Services: payments-service.\n\n"
        "Symptom: a partner SDK reused idempotency keys across distinct charges; "
        "legitimate charges were rejected as duplicates (~0.4% of partner traffic).\n\n"
        "Resolution: key scope tightened to (merchant, amount, card-fingerprint) with a "
        "compatibility window; partner notified and SDK fixed.\n\n"
        "Resolved by: dana-chen (payments platform). Duration: 3 hours (non-paging).",
        ["incident", "payments-service", "P2"],
        RESOLVED,
    ),
    _issue(
        "P1 2026-02-06: payments-service p99 degradation from ORM N+1 on invoice listing",
        "Severity: P1. Date: 2026-02-06. Services: payments-service, payments-db-primary.\n\n"
        "Symptom: invoice listing endpoint issued one query per line item after an ORM "
        "upgrade dropped an eager-load annotation; DB query volume tripled and p99 "
        "degraded to 1800ms at peak.\n\n"
        "Resolution: eager-load restored; query-count regression test added to CI.\n\n"
        "Resolved by: dana-chen (payments platform). Duration: 47 minutes.",
        ["incident", "payments-service", "P1"],
        RESOLVED,
    ),
    _issue(
        "P2 2026-01-23: payments-service duplicate pager alerts — alert dedupe fix",
        "Severity: P2. Date: 2026-01-23. Services: payments-service.\n\n"
        "Symptom: every p99 threshold crossing paged twice (two alert rules with "
        "overlapping windows); on-call fatigue, no customer impact.\n\n"
        "Resolution: alert rules consolidated; dedupe key added on (service, metric, "
        "window).\n\n"
        "Resolved by: miguel-santos (payments platform, rotation B). Duration: 1 day "
        "(non-paging).",
        ["incident", "payments-service", "P2"],
        RESOLVED,
    ),
    # --- INC-2289: the second postmortem mirror (alex-kim, db-primary) ---
    _issue(
        "[INC-2289] P1 2026-03-02: payments-db-primary pool exhaustion during settlement batch",
        "Severity: P1. Date: 2026-03-02. Services: payments-db-primary, payments-service "
        "(degraded, no SLO breach).\n\n"
        "Symptom: nightly settlement batch rescheduled into the early-morning traffic ramp; "
        "its connection fan-out pushed pool_used from ~40 to 100 over six minutes starting "
        "06:12 UTC. payments-service p99 degraded to ~1900ms.\n\n"
        "Resolution: pool exhaustion runbook steps 2-4-5 — identified settlement-batch via "
        "pg_stat_activity, killed idle-in-transaction sessions, paused the batch scheduler "
        "entry. Pool headroom recovered without a ceiling raise.\n\n"
        "Root cause: batch schedule change reviewed without a capacity check; batch held "
        "transactions open across network calls.\n\n"
        "Resolved by: alex-kim (database reliability). Duration: 31 minutes. "
        "Postmortem: INC-2289 (in Senso).",
        ["incident", "payments-db-primary", "P1", "postmortem"],
        RESOLVED,
    ),
    _issue(
        "Migrate settlement batch to payments-db read replica (INC-2289 follow-up, PAY-1872)",
        "Follow-up from INC-2289 (2026-03-02): batch workloads belong on the read replica. "
        "The settlement batch still runs against payments-db-primary and still holds "
        "transactions open across network calls — the same consumer implicated in both "
        "pool-exhaustion incidents this year.\n\n"
        "Suggested owner: alex-kim (database reliability). Tracked previously as PAY-1872.",
        ["follow-up", "payments-db-primary", "settlement-batch"],
        OPEN,
    ),
    _issue(
        "P2 2026-05-15: checkout-service cache stampede after Redis upgrade",
        "Severity: P2. Date: 2026-05-15. Services: checkout-service.\n\n"
        "Symptom: Redis minor upgrade flushed the cart cache; cold-cache stampede pushed "
        "checkout-service p99 to 600ms for 12 minutes. payments-service healthy throughout "
        "(checkout-local case per the checkout degradation runbook).\n\n"
        "Resolution: request-coalescing flag enabled (runbook step 2); cache warmed.\n\n"
        "Resolved by: priya-raman (storefront). Duration: 16 minutes.",
        ["incident", "checkout-service", "P2"],
        RESOLVED,
    ),
    _issue(
        "Add sustained pool_used > 60 alert on payments-db-primary (INC-2417 lesson)",
        "From the INC-2417 postmortem (2026-04-18): the pool climb was visible minutes "
        "before customer impact; alerting on pool_used > 60 sustained would have bought "
        "~4 minutes of lead time before the p99 SLO breach.\n\n"
        "STILL OPEN — deprioritized in the 2026-04 sprint. Both pool-exhaustion incidents "
        "this year (INC-2289, INC-2417) would have been caught earlier by this alert.\n\n"
        "Suggested owner: alex-kim (database reliability), with dana-chen (payments "
        "platform) reviewing thresholds.",
        ["follow-up", "payments-db-primary", "alerting"],
        OPEN,
    ),
]


def get_client():
    os.environ.setdefault(
        "COMPOSIO_CACHE_DIR", os.path.join(tempfile.gettempdir(), "composio-cache")
    )
    from composio import Composio

    # Empty env key falls through to the SDK's cached login (~/.composio) —
    # the same auth composio_link.py --check verified ACTIVE.
    api_key = os.environ.get("COMPOSIO_API_KEY", "").strip()
    client = Composio(api_key=api_key) if api_key else Composio()
    return client, os.environ.get("COMPOSIO_USER_ID", "").strip() or "incident-sherpa"


def execute(client, user_id: str, slug: str, args: dict) -> dict:
    response = client.tools.execute(
        slug, arguments=args, user_id=user_id, dangerously_skip_version_check=True
    )
    if isinstance(response, dict) and response.get("successful") is False:
        raise RuntimeError(f"{slug} failed: {str(response.get('error'))[:500]}")
    return response


def ensure_project(client, user_id: str) -> None:
    """Create PLAT if absent (idempotent re-runs)."""
    listing = execute(client, user_id, "JIRA_GET_ALL_PROJECTS", {})
    values = listing.get("data", {}).get("data", {}).get("values", [])
    if any(p.get("key") == PROJECT_KEY for p in values):
        print(f"project {PROJECT_KEY} already exists")
        return
    me = execute(client, user_id, "JIRA_GET_CURRENT_USER", {})
    lead = me["data"]["accountId"]
    last_error: Exception | None = None
    for template in PROJECT_TEMPLATES:
        try:
            execute(
                client,
                user_id,
                "JIRA_CREATE_PROJECT",
                {
                    "key": PROJECT_KEY,
                    "name": PROJECT_NAME,
                    "project_type_key": "software",
                    "project_template_key": template,
                    "lead_account_id": lead,
                },
            )
            print(f"created project {PROJECT_KEY} ({template})")
            return
        except Exception as exc:  # try the next template shape
            last_error = exc
    raise RuntimeError(f"could not create project {PROJECT_KEY}: {last_error}")


def create_issues(client, user_id: str) -> list[tuple[str, str]]:
    """Create every issue; returns [(key, target_status)]. Skips already-seeded
    summaries so re-runs do not duplicate."""
    existing = execute(
        client,
        user_id,
        "JIRA_SEARCH_FOR_ISSUES_USING_JQL_POST",
        {"jql": f'project = {PROJECT_KEY}', "fields": ["summary"], "max_results": 100},
    )
    issues = existing.get("data", {}).get("issues", []) or existing.get("data", {}).get(
        "data", {}
    ).get("issues", [])
    # Composio flattens the REST shape: summary/key/status are top-level.
    seeded = {i["summary"]: i["key"] for i in issues}

    created: list[tuple[str, str]] = []
    for spec in ISSUES:
        if spec["summary"] in seeded:
            print(f"skip (exists): {spec['summary'][:60]}")
            created.append((seeded[spec["summary"]], spec["status"]))
            continue
        args = {
            "project_key": PROJECT_KEY,
            "issue_type": "Task",
            "summary": spec["summary"],
            "description": spec["description"],
            "labels": spec["labels"],
        }
        try:
            response = execute(client, user_id, "JIRA_CREATE_ISSUE", args)
        except RuntimeError as exc:
            if "label" not in str(exc).lower():
                raise
            args.pop("labels")  # labels unsupported by this tool version — degrade loudly
            print(f"labels rejected, retrying without: {spec['summary'][:50]}")
            response = execute(client, user_id, "JIRA_CREATE_ISSUE", args)
        key = response["data"].get("key") or response["data"].get("data", {}).get("key")
        created.append((key, spec["status"]))
        print(f"created {key}: {spec['summary'][:70]}")
    return created


def transition_done(client, user_id: str, created: list[tuple[str, str]]) -> None:
    """Move RESOLVED-status issues to Done (transition id discovered once)."""
    done_targets = [key for key, status in created if status == RESOLVED]
    if not done_targets:
        return
    transitions = execute(
        client, user_id, "JIRA_GET_TRANSITIONS", {"issue_id_or_key": done_targets[0]}
    )
    options = transitions.get("data", {}).get("transitions", []) or transitions.get(
        "data", {}
    ).get("data", {}).get("transitions", [])
    done_id = next(
        (t["id"] for t in options if t.get("to", {}).get("name") == RESOLVED), None
    )
    if done_id is None:
        print(f"WARNING: no '{RESOLVED}' transition found ({[t.get('name') for t in options]}) "
              "— issues left in To Do")
        return
    for key in done_targets:
        execute(
            client,
            user_id,
            "JIRA_TRANSITION_ISSUE",
            {"issue_id_or_key": key, "transition_id_or_name": done_id},
        )
        print(f"transitioned {key} -> {RESOLVED}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="print the authored issues only")
    args = parser.parse_args(argv)

    dana = sum(1 for i in ISSUES if "Resolved by: dana-chen" in i["description"])
    payments = sum(1 for i in ISSUES if "payments-service" in i["labels"])
    print(f"authored {len(ISSUES)} issues; payments-service incidents: {payments}, "
          f"dana-chen resolved: {dana} (ownership map says 9 of 12)")
    if dana != 9 or payments != 12:
        print("FATAL: authored history contradicts the Senso ownership map", file=sys.stderr)
        return 2
    if args.dry_run:
        for spec in ISSUES:
            print(f"  [{spec['status']:5}] {spec['summary']}")
        return 0

    client, user_id = get_client()
    ensure_project(client, user_id)
    created = create_issues(client, user_id)
    transition_done(client, user_id, created)
    print(f"seeded {len(created)} issues into {PROJECT_KEY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
