# Composio B7 — Slack/Jira connection debug session

Date: 2026-06-12 (afternoon, ~2:25–3:16 PM PDT)
Scope: complete the Composio integration (BUILD-STATE.md **B7**) and resolve a
reported "Airbyte not connected to Slack/Jira" issue.

TL;DR: the reported issue was **not** Airbyte. The Slack/Jira integration is
Composio's job, and it was actually working — a buggy verification script plus a
stale duplicate OAuth account made Jira *look* disconnected. Both are now fixed.
B7 is satisfied: `slack: ACTIVE`, `jira: ACTIVE`.

---

## 1. Starting point

- `libs/composio_actions/send.py` (the single outbound-action choke point) was
  pre-authored but its SDK contract was an **unverified guess**, flagged for
  on-site confirmation.
- `COMPOSIO_API_KEY` was empty; no Slack/Jira OAuth had been done.
- `composio` SDK was not installed in `.venv`.

## 2. SDK contract verification (the Pioneer lesson, again)

Installed `composio==0.13.1` (core reports `1.0.0-rc2`) and introspected the
**installed** API surface (`dir()` / `inspect.signature`) rather than trusting
docs or memory. The authored contract was wrong on every point:

| Authored guess (wrong) | Real, verified SDK |
|---|---|
| `session = composio.create(user_id=...)` then `session.tools.execute(...)` | No per-call session. `tools`, `connected_accounts`, `toolkits` hang off the `Composio` instance. |
| `session.tools.execute(slug, arguments=...)` | `client.tools.execute(slug, arguments=..., user_id=...)` — routes to the user's connected account by `user_id`. |
| `session.link()` | `connected_accounts.link(user_id, auth_config_id)` or the higher-level `toolkits.authorize(user_id=..., toolkit=...)` → `ConnectionRequest(.redirect_url, .wait_for_connection())`. `initiate()` exists but is the deprecated path. |
| (cache dir unhandled) | SDK creates `~/.composio` **at import** — crashes on a read-only home. Pin `COMPOSIO_CACHE_DIR` to a writable dir. |

### Code changes (committed `fcdce17`)
- `libs/composio_actions/send.py`:
  - `_get_session` → `_get_client`, returns the `Composio` instance (no session).
  - `tools.execute(slug, arguments=..., user_id=...)` with a `_composio_user_id()`
    helper (env `COMPOSIO_USER_ID`, default `incident-sherpa`).
  - `COMPOSIO_CACHE_DIR` guard (`tempfile.gettempdir()/composio-cache`) so a
    read-only container home cannot crash the import.
- `tests/test_choke_point.py`: updated the structure test for the rename
  (`_get_session` → `_get_client`). All 15 choke-point tests + full suite (83) green.
- `scripts/composio_link.py`: **new** one-time OAuth + verification helper
  (`toolkits.authorize` for slack + jira, `--check` verify gate, `--schema`
  prints live tool input fields). Never uses `initiate()`.
- `.env` / `.env.example`: `COMPOSIO_USER_ID`, `SLACK_INCIDENT_CHANNEL`,
  `JIRA_PROJECT_KEY` + run instructions; `.gitignore` adds `.composio-cache/`.

## 3. Credentials (human/UI steps)

1. **API key**: composio.dev dashboard → Settings → API keys → create `0612hack`.
   Permissions: Full access is fine; minimal scope = Tool execution (Full),
   Connected accounts (Full), Auth configs (Read), Tools (Read).
   Key landed in `.env`: `COMPOSIO_API_KEY=ak_REDACTED`.
2. **Toolkits**: dashboard → Toolkits → enable **Slack** and **Jira** with
   Composio-managed OAuth (creates the auth configs `authorize()` uses).
3. **OAuth**: `python3 scripts/composio_link.py` opens browser consent for each;
   waits until ACTIVE. (Done out-of-band; both connected.)

`.env` config used:
```
COMPOSIO_API_KEY=ak_REDACTED
COMPOSIO_USER_ID=incident-sherpa
SLACK_INCIDENT_CHANNEL=#incidents
JIRA_PROJECT_KEY=SCRUM   # site incidentsherpa.atlassian.net, project "Sherpa"
```

## 4. The reported "Airbyte not connected to Slack/Jira" issue

### Symptom
`python3 scripts/composio_link.py --check` reported:
```
jira: EXPIRED
slack: ACTIVE
B7 verification: XX jira: EXPIRED
```

### Investigation
Listing all connected accounts for `user_id=incident-sherpa` revealed **two**
Jira accounts, not one:
```
acct: jira | id: ca_rU2KdScaPTrS | status: ACTIVE      <- working
acct: jira | id: ca_E8J8erFHn2BN | status: EXPIRED     <- stale duplicate
acct: slack| id: ca_S9q6EsLdRVGa | status: ACTIVE
```
Attempting `connected_accounts.refresh("ca_E8J8erFHn2BN")` failed with:
```
400 ConnectedAccount_MissingRequiredFields:
"Missing required fields: Your Subdomain (example: 'your-subdomain' for
'your-subdomain.atlassian.net')"
```
i.e. the EXPIRED account was created by a first OAuth attempt that never
captured the Atlassian cloud subdomain — it could never be refreshed.

### Root cause (two parts)
1. **Script bug**: `_active_toolkits` mapped `slug -> status` with
   last-write-wins, so the stale EXPIRED Jira account overwrote the ACTIVE one
   in the report. Jira was in fact connected.
2. **Stale duplicate**: the unrefreshable EXPIRED Jira account was a hazard —
   `tools.execute` could route a real Jira create to it mid-demo.

Airbyte was never involved. Airbyte (B5) is keyed and only pulls GitHub/Jira
**history** into ClickHouse; it does not touch Slack and is unrelated to
outbound actions.

### Fixes applied
- **Deleted** the stale EXPIRED Jira account `ca_E8J8erFHn2BN`
  (`connected_accounts.delete`).
- **Fixed `scripts/composio_link.py`** (committed `9c75690`): a toolkit counts
  as ACTIVE if **any** of its accounts is ACTIVE; the listing prints every
  account (`slug + id + status`) so duplicates are visible. Added a
  `_list_accounts` helper.

### Verification after fix
```
Existing connected accounts:
  - jira: ACTIVE (ca_rU2KdScaPTrS)
  - slack: ACTIVE (ca_S9q6EsLdRVGa)
=== B7 verification ===
  OK  slack: ACTIVE
  OK  jira: ACTIVE
All requested Composio connections are ACTIVE — B7 satisfied.
```

## 5. Live tool-schema confirmation (last flagged item)

`--schema` against the live API confirmed the argument field names used by
`_action_arguments`:
- `JIRA_CREATE_ISSUE`: `project_key`, `issue_type`, `summary`, `description` — **match**.
- `SLACK_SEND_MESSAGE`: fields are `blocks, channel, fallback_text,
  markdown_text, reply_broadcast, thread_ts, unfurl_links, unfurl_media` —
  **there is NO `text` field**. The message body must be `markdown_text`.
  (The background loop had already corrected this in commit `886350d`, verified
  by real Slack + Jira sends, so `send.py` already sends `markdown_text`.)

## 6. Side fix — Guild PAT quoting (same session)

`GUILD_PAT` in `.env` was wrapped in literal double-quotes. `libs/guild/
session.py` only `.strip()`s whitespace, not quotes, so a quote-preserving
loader would send `Bearer "u.eJw…"`. Live test against `GET app.guild.ai/api/me`:
- clean token → **HTTP 200** (authenticated)
- quoted token → **HTTP 401 Unauthorized**

Removed the quotes from `GUILD_PAT`. (ClickHouse/Langfuse quoted values were
left as-is — their live tests already pass, so that loader strips quotes.)

## 7. Commits from this session

| Commit | Summary |
|---|---|
| `fcdce17` | fix(composio): correct SDK contract to verified composio 0.13.1 + add B7 link script |
| `886350d` | fix(composio): live-API contract — markdown_text + skip_version_check (verified by real Slack+Jira sends) *(background loop)* |
| `9c75690` | fix(composio): --check counts a toolkit ACTIVE if ANY account is active |

`.env` changes (gitignored, not committed): Composio key + user_id + targets,
Guild PAT de-quoted.

## 8. Final status

- **B7 (Composio Slack/Jira)**: ✅ satisfied — both connections ACTIVE; choke
  point sends `markdown_text` (Slack) and the correct Jira fields; verified
  end-to-end by real sends (loop commit `886350d`).
- **Airbyte (B5)**: unaffected; was never the cause.
- Tests: `tests/test_choke_point.py` 15 passed; ruff clean.

## 9. Reusable commands

```bash
source .venv/bin/activate

# Verify both connections (B7 gate; exit 0 when all ACTIVE)
python3 scripts/composio_link.py --check

# Authorize a missing/expired toolkit via browser OAuth
python3 scripts/composio_link.py --toolkits jira

# Print the live input field names for the two actions
python3 scripts/composio_link.py --check --schema
```

Pitfalls learned:
- The SDK has no "session" — everything hangs off the `Composio` instance.
- `tools.execute` needs `user_id=` to route to the connected account; it must
  match `COMPOSIO_USER_ID` / the id used at link time.
- Pin `COMPOSIO_CACHE_DIR` on read-only container homes.
- A toolkit can have multiple connected accounts; an EXPIRED duplicate that
  lacks the Atlassian subdomain can never be refreshed — delete it.
- Slack body field is `markdown_text`, not `text`.
