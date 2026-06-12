#!/usr/bin/env python3
"""B7 one-time setup + verification: authorize Slack + Jira via Composio OAuth.

This is the T+0:10 gate. Run it ONCE after COMPOSIO_API_KEY lands in .env to
connect the agent's Slack workspace (chat:write) and Jira project (create).
It uses the verified SDK contract — `toolkits.authorize()` /
`connected_accounts.link()`, NEVER the deprecated `initiate()`.

Flow per toolkit:
  1. toolkits.authorize(user_id, toolkit) -> ConnectionRequest(redirect_url)
  2. open redirect_url in your browser, approve the OAuth consent
  3. wait_for_connection() blocks until the account is ACTIVE

The user_id MUST match libs/composio_actions/send.py (_composio_user_id):
COMPOSIO_USER_ID or the "incident-sherpa" default.

Usage:
    python3 scripts/composio_link.py              # authorize slack + jira (OAuth)
    python3 scripts/composio_link.py --check       # verify only: list connections
    python3 scripts/composio_link.py --toolkits slack
    python3 scripts/composio_link.py --schema      # also print live tool arg schemas

Exit code 0 only when every requested toolkit has an ACTIVE connection.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Toolkit slug -> the action this project sends through it. The action slugs
# are the ones the choke point (libs/composio_actions/send.py) executes.
TOOLKIT_ACTIONS: dict[str, str] = {
    "slack": "SLACK_SEND_MESSAGE",
    "jira": "JIRA_CREATE_ISSUE",
}

WAIT_TIMEOUT_SECONDS = 180.0


def _load_env_file() -> None:
    """Populate os.environ from repo .env for vars not already set.

    The app reads os.environ directly (no dotenv dependency); this keeps the
    script ergonomic when the key lives in .env. Existing env wins.
    """
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _user_id() -> str:
    return os.environ.get("COMPOSIO_USER_ID", "").strip() or "incident-sherpa"


def _build_client():
    api_key = os.environ.get("COMPOSIO_API_KEY", "").strip()
    if not api_key:
        print(
            "COMPOSIO_API_KEY is unset. Get it from composio.dev -> dashboard -> "
            "API keys, put it in .env, then re-run. (BUILD-STATE.md B7)",
            file=sys.stderr,
        )
        raise SystemExit(2)
    # Same cache-dir guard as the lib: a read-only home must not crash import.
    os.environ.setdefault(
        "COMPOSIO_CACHE_DIR", os.path.join(tempfile.gettempdir(), "composio-cache")
    )
    from composio import Composio

    return Composio(api_key=api_key)


def _list_accounts(client, user_id: str) -> list[tuple[str, str, str]]:
    """Return [(toolkit_slug_lower, account_id, status)] for this user."""
    rows: list[tuple[str, str, str]] = []
    try:
        accounts = client.connected_accounts.list(user_ids=[user_id])
    except Exception as exc:  # noqa: BLE001 - surface the real API error
        print(f"could not list connected accounts: {exc}", file=sys.stderr)
        return rows
    items = getattr(accounts, "items", None) or getattr(accounts, "data", None) or []
    for acct in items:
        toolkit = getattr(acct, "toolkit", None)
        slug = getattr(toolkit, "slug", None) or getattr(acct, "toolkit_slug", None)
        if slug:
            acct_id = str(getattr(acct, "id", ""))
            status = str(getattr(acct, "status", "UNKNOWN"))
            rows.append((str(slug).lower(), acct_id, status))
    return rows


def _active_toolkits(client, user_id: str) -> dict[str, str]:
    """Map toolkit_slug(lower) -> best status. A toolkit counts as ACTIVE if
    ANY of its connected accounts is ACTIVE (a stale EXPIRED duplicate must not
    mask a working connection — the last-write-wins bug this replaces)."""
    found: dict[str, str] = {}
    for slug, _id, status in _list_accounts(client, user_id):
        prev = found.get(slug)
        if prev is None or status.upper() == "ACTIVE":
            found[slug] = status
    return found


def _authorize(client, user_id: str, toolkit: str) -> str:
    """Run the OAuth handshake for one toolkit. Returns final status."""
    print(f"\n=== {toolkit} ===")
    request = client.toolkits.authorize(user_id=user_id, toolkit=toolkit)
    redirect_url = getattr(request, "redirect_url", None)
    if redirect_url:
        print("Open this URL in your browser and approve access:")
        print(f"  {redirect_url}")
    else:
        print("No redirect URL returned — the account may already be connected.")
    print(f"Waiting up to {int(WAIT_TIMEOUT_SECONDS)}s for the connection to go ACTIVE...")
    try:
        account = request.wait_for_connection(timeout=WAIT_TIMEOUT_SECONDS)
        status = getattr(account, "status", "ACTIVE")
        print(f"  -> {toolkit} connection status: {status}")
        return str(status)
    except Exception as exc:  # noqa: BLE001 - report and let caller mark failure
        print(f"  -> {toolkit} did not connect: {exc}", file=sys.stderr)
        return "FAILED"


def _print_tool_schema(client, action: str) -> None:
    """Print a tool's live input field names — confirms _action_arguments()."""
    try:
        tool = client.tools.get_raw_composio_tool_by_slug(action)
    except Exception as exc:  # noqa: BLE001
        print(f"  ({action}: could not fetch schema: {exc})")
        return
    schema = (
        getattr(tool, "input_parameters", None)
        or getattr(tool, "input_schema", None)
        or getattr(tool, "parameters", None)
    )
    props = getattr(schema, "properties", None)
    if props is None and isinstance(schema, dict):
        props = schema.get("properties")
    fields = sorted(props.keys()) if isinstance(props, dict) else schema
    print(f"  {action} input fields: {fields}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--toolkits",
        nargs="+",
        default=list(TOOLKIT_ACTIONS),
        choices=list(TOOLKIT_ACTIONS),
        help="which toolkits to authorize/verify (default: slack jira)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify only — list connections, do not start OAuth",
    )
    parser.add_argument(
        "--schema",
        action="store_true",
        help="also print each tool's live input field names",
    )
    args = parser.parse_args(argv)

    _load_env_file()
    client = _build_client()
    user_id = _user_id()
    print(f"Composio user_id: {user_id}")

    rows = _list_accounts(client, user_id)
    if rows:
        print("Existing connected accounts:")
        for slug, acct_id, status in sorted(rows):
            flag = "" if status.upper() == "ACTIVE" else "   <-- not usable"
            print(f"  - {slug}: {status} ({acct_id}){flag}")
    elif args.check:
        print("No connected accounts found for this user_id.")
    existing = _active_toolkits(client, user_id)

    results: dict[str, str] = {}
    for toolkit in args.toolkits:
        current = existing.get(toolkit, "")
        if current.upper() == "ACTIVE":
            print(f"\n=== {toolkit} === already ACTIVE, skipping OAuth")
            results[toolkit] = "ACTIVE"
        elif args.check:
            results[toolkit] = current or "MISSING"
        else:
            results[toolkit] = _authorize(client, user_id, toolkit)

    if args.schema:
        print("\n=== live tool input schemas ===")
        for toolkit in args.toolkits:
            _print_tool_schema(client, TOOLKIT_ACTIONS[toolkit])

    print("\n=== B7 verification ===")
    all_active = True
    for toolkit, status in results.items():
        ok = status.upper() == "ACTIVE"
        all_active = all_active and ok
        print(f"  {'OK ' if ok else 'XX '} {toolkit}: {status}")
    if all_active:
        print("All requested Composio connections are ACTIVE — B7 satisfied.")
        return 0
    print("Some connections are not ACTIVE — re-run without --check to authorize.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
