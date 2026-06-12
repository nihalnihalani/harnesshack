#!/usr/bin/env python3
"""Seed the demo Slack workspace ("Sherpa") for the 3-minute demo.

demo-scripts.md pre-staging requires "#incidents has one prior SHERPA
message". This seeds exactly that — a prior structured update for INC-2417 in
the same format build_slack_update_text emits (so the live Composio post at
demo beat 1:25 matches the channel's history) — plus a small amount of honest
human context that cross-links the REAL seeded Jira tickets (PLAT-14/16), and
two texture channels (#eng-payments, #deploys).

Numbers discipline: INC-2417 figures (09:41 climb, 09:45:30 breach, ~4 min
lead, pool 100 -> 150, 22 min) come verbatim from the Senso postmortem
(scripts/seed_senso.py). Nothing here invents a latency or severity.

Sends go through the already-authorized Composio Slack connection (B7 ACTIVE)
— the same surface the live agent uses; messages appear as the connected user,
exactly like the live demo send will.

Usage:
    python3 scripts/seed_slack_history.py [--dry-run]
"""

from __future__ import annotations

import argparse
import os
import tempfile

INCIDENTS_CHANNEL = "incidents"
INCIDENTS_TOPIC = (
    "P0/P1 coordination — IncidentSherpa posts structured updates here. "
    "Runbooks + postmortems live in Senso."
)

# (channel, purpose, [messages]) — first #incidents message gets pinned.
SEED_PLAN: list[tuple[str, str, list[str]]] = [
    (
        INCIDENTS_CHANNEL,
        "Live incident coordination. The agent is the stenographer in the room.",
        [
            # The prior SHERPA message — same shape as build_slack_update_text.
            ":rotating_light: Incident INC-2417 — state: RESOLVED\n"
            "Causal chain: payments-db-primary pool exhaustion (09:41 UTC) → "
            "payments-service p99 SLO breach (09:45:30 UTC) — the pool climb preceded "
            "the breach by ~4 minutes\n"
            "Suggested owner — awaiting confirmation: dana-chen",
            "confirming dana-chen as owner for INC-2417. runbook step 3 applied "
            "(pool ceiling 100 → 150), p99 recovered — 22 minutes end to end.",
            "INC-2417 postmortem is published in Senso. the open action item is the "
            "sustained pool_used > 60 alert — tracked as PLAT-16, still in the backlog. "
            "don't let it rot.",
        ],
    ),
    (
        "eng-payments",
        "payments-service + payments-db-primary engineering",
        [
            "heads up: the settlement batch is still running against payments-db-primary "
            "(migration to the read replica is PLAT-14, not started). until that lands, "
            "keep an eye on pool_used during the morning ramp.",
            "pool metrics exporter is live — pool_used / pool_max now flowing to the "
            "metrics pipeline at 5s resolution. this is what the INC-2417 postmortem "
            "asked for.",
        ],
    ),
    (
        "deploys",
        "production deploy log",
        [
            "payments-service v2.41.1 → prod. rollback fix for the canary p99 regression "
            "(PLAT-1).",
            "checkout-service v3.12.2 → prod. request-coalescing flag now default-on "
            "(PLAT-15 follow-up).",
        ],
    ),
]


def get_client():
    os.environ.setdefault(
        "COMPOSIO_CACHE_DIR", os.path.join(tempfile.gettempdir(), "composio-cache")
    )
    from composio import Composio

    api_key = os.environ.get("COMPOSIO_API_KEY", "").strip()
    client = Composio(api_key=api_key) if api_key else Composio()
    return client, os.environ.get("COMPOSIO_USER_ID", "").strip() or "incident-sherpa"


def execute(client, user_id: str, slug: str, args: dict) -> dict:
    response = client.tools.execute(
        slug, arguments=args, user_id=user_id, dangerously_skip_version_check=True
    )
    if isinstance(response, dict) and response.get("successful") is False:
        raise RuntimeError(f"{slug} failed: {str(response.get('error'))[:300]}")
    return response


def channel_ids_by_name(client, user_id: str) -> dict[str, str]:
    listing = execute(
        client, user_id, "SLACK_LIST_ALL_CHANNELS", {"limit": 200}
    )
    channels = listing.get("data", {}).get("channels", [])
    return {ch["name"]: ch["id"] for ch in channels}


def ensure_channel(client, user_id: str, existing: dict[str, str], name: str) -> str:
    if name in existing:
        print(f"channel #{name} exists ({existing[name]})")
        return existing[name]
    response = execute(client, user_id, "SLACK_CREATE_CHANNEL", {"name": name})
    channel = response.get("data", {}).get("channel", {})
    channel_id = channel.get("id")
    if not channel_id:
        raise RuntimeError(f"SLACK_CREATE_CHANNEL returned no id for #{name}")
    print(f"created channel #{name} ({channel_id})")
    existing[name] = channel_id
    return channel_id


def posted_texts(client, user_id: str, channel_id: str) -> set[str]:
    """First lines of real (non-system) messages already in the channel —
    join/topic events carry a subtype and are not content."""
    history = execute(
        client,
        user_id,
        "SLACK_FETCH_CONVERSATION_HISTORY",
        {"channel": channel_id, "limit": 50},
    )
    messages = history.get("data", {}).get("messages", [])
    return {
        m.get("text", "").splitlines()[0].strip()
        for m in messages
        if not m.get("subtype") and m.get("text")
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="print the plan only")
    args = parser.parse_args(argv)

    if args.dry_run:
        for name, _purpose, messages in SEED_PLAN:
            print(f"#{name}: {len(messages)} messages")
            for m in messages:
                print(f"   - {m.splitlines()[0][:90]}")
        return 0

    client, user_id = get_client()
    existing = channel_ids_by_name(client, user_id)

    for name, purpose, messages in SEED_PLAN:
        channel_id = ensure_channel(client, user_id, existing, name)
        seen = posted_texts(client, user_id, channel_id)
        try:
            execute(
                client,
                user_id,
                "SLACK_SET_CONVERSATION_PURPOSE",
                {"channel": channel_id, "purpose": purpose},
            )
        except RuntimeError as exc:
            print(f"purpose skipped for #{name}: {exc}")
        for index, text in enumerate(messages):
            if text.splitlines()[0].strip() in seen:
                print(f"skip (posted): {text.splitlines()[0][:60]}")
                continue
            response = execute(
                client,
                user_id,
                "SLACK_SEND_MESSAGE",
                {"channel": channel_id, "markdown_text": text},
            )
            ts = response.get("data", {}).get("ts") or response.get("data", {}).get(
                "message", {}
            ).get("ts")
            print(f"posted to #{name}: {text.splitlines()[0][:70]}")
            if name == INCIDENTS_CHANNEL and index == 0 and ts:
                try:
                    execute(
                        client,
                        user_id,
                        "SLACK_PIN_ITEM",
                        {"channel": channel_id, "timestamp": ts},
                    )
                    print("pinned the prior SHERPA message")
                except RuntimeError as exc:
                    print(f"pin skipped: {exc}")

    try:
        execute(
            client,
            user_id,
            "SLACK_SET_THE_TOPIC_OF_A_CONVERSATION",
            {"channel": existing[INCIDENTS_CHANNEL], "topic": INCIDENTS_TOPIC},
        )
        print("set #incidents topic")
    except RuntimeError as exc:
        print(f"topic skipped: {exc}")

    print("slack seeding complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
