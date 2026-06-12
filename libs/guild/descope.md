# Guild descope path — REST-first session client

> Read this before touching `libs/guild/` (CLAUDE.md project structure note).

## The decision

**`libs/guild/` is built REST-first.** The `@guildai/agents-sdk` upgrade path is
optional and additive — never a rewrite.

## Why (cite: BUILD-STATE.md DECISIONS, 2026-06-12)

The T+0 Guild gate (CLAUDE.md Go/No-Go Gate 1, 15-min hard cap) ran the probe:

```
$ npm view @guildai/agents-sdk version
npm error 401 Unauthorized - GET https://app.guild.ai/npm/@guildai%2fagents-sdk
```

The SDK lives on Guild's **private npm registry** (`app.guild.ai/npm`) and 401s
without auth — it is not on public npm. Per the gate's descope branch, Guild
stays **load-bearing** through its REST surface: sessions, append-only audit
events, credential scoping. Only the SDK convenience layer is descoped.

## What the REST client does (`libs/guild/session.py`)

| Function | Endpoint (convention) | Purpose |
|---|---|---|
| `create_session(incident_id)` | `POST /v1/sessions` | One Guild session per incident |
| `append_audit_event(session_id, typed_event)` | `POST /v1/sessions/{id}/events` | Append ONE typed event — the audit trail is append-only by construction (no update/delete exists in the module) |
| `close_session(session_id)` | `POST /v1/sessions/{id}/close` | Close on Resolve |

Auth: `Authorization: Bearer $GUILD_PAT` against `$GUILD_API_BASE`. Both env
vars are **B1** (BUILD-STATE.md BLOCKERS); the client raises
`NotConfiguredError` naming B1 while either is unset — no fake sessions, ever.

## On-site confirmation checklist (when B1 lands)

Guild's REST docs were not publicly verifiable at authoring time (open beta
since 2026-04-29; account "may need a Guild contact", sponsors.md). Confirm
with the sponsor rep:

1. Exact session endpoints (`/v1/sessions`, `/{id}/events`, `/{id}/close`) and
   the audit-event body shape (`session.py` builders are the single place to fix).
2. Session-create response field for the id (`id` / `session_id` — the parser
   tolerates both but fails loudly on neither).
3. Whether `GUILD_PAT` also grants the private npm registry — if yes, the SDK
   becomes an optional upgrade for credential scoping/triggers, layered ON TOP
   of this REST client.

## Escalation ladder (from CLAUDE.md Gate 1)

REST also dead → escalate to the Guild sponsor rep; last resort: LangGraph
state + drop ONLY the Guild prize claim. Do not silently fake an audit trail.
