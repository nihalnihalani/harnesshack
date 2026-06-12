# Demo Scripts — Round 3/4 (Rev 2.1)

Note: the IncidentSherpa script below incorporates the Round 4 Pioneer fix — severity/blast-radius extraction uses **GLiNER2 schema-conditioned inference** (GLiNER2 is designed for arbitrary-schema span/class extraction). GLiGuard is retained only in its actual role: a safety guardrail on outbound text (Slack messages, Jira descriptions, postmortem).

---

## Demo script: IncidentSherpa (Rev 2.1) — INVERTED ARC

**Target runtime:** 3:00. **Station:** one laptop, OpenUI timeline pre-loaded mid-incident, tabs: Langfuse, Airbyte, Slack, Jira, Render. Presenter mode 125%.

### (a) Timestamped beats

```
0:00–0:08 | SCREEN: OpenUI incident timeline, already 8 min into a P1.
          | Typed event log on left:
          |  "02:14:01 — PagerDuty alert ingested: payments-service p99 > 2400ms"
          |  "02:14:03 — Pioneer/GLiNER2 severity extraction (schema-conditioned): P1, blast radius
          |    payments + checkout + reporting" (red badge)
          |  "02:14:07 — ClickHouse causal query complete"
          |  "02:17:43 — Runbook from Senso: step 3 resolved identical spike
          |    in 8 min on 2026-04-11"
          |  "02:20:09 — Composio: Slack status posted to #incidents"
          | Guild state-machine stepper at top: [Investigating ✓][Mitigating •][Resolved]
          | PRESENTER: "This incident has been live for eight minutes. Every
          | action the agent took is in this log. No one typed it. Let me show
          | you what happens when I click Resolve."

0:08–0:12 | CLICK "Incident Resolved". Stepper advances to [Resolved •].
          | Postmortem panel fades in with skeleton shimmer.

0:12–0:30 | *** WOW MOMENT *** Postmortem streams token-by-token:
          |  "## Incident Postmortem — 2026-06-12 02:14 UTC
          |   Duration: 8 min 14 sec
          |   Severity: P1 (Pioneer/GLiNER2 schema extraction, <100ms)
          |   Root cause: DB connection pool exhausted on payments-db-primary
          |     at 02:09:51, preceding latency spike by 4m10s (ClickHouse
          |     lag/lead window).
          |   Suggested owner: @dana-chen (9 of last 12 payments incidents)
          |   Remediation: runbook step 3 — pool ceiling raised to 200.
          |   Action items: [ ] @dana-chen pool-ceiling alert at 80%;
          |     [ ] Jira PLAT-4417 created."
          | PRESENTER: "Complete postmortem. In eighteen seconds. Because the
          | agent was the stenographer in the room — not a journalist
          | reconstructing from Slack two days later."

0:30–0:38 | Jira badge appears: "PLAT-4417 — Suggested owner: dana-chen —
          | awaiting confirmation."
          | PRESENTER: "Owner suggested, not assigned — ownership maps go
          | stale and we don't auto-assign P1s without a human confirming.
          | Now let me rewind. Let me show you how we got here."

0:38–0:42 | CLICK "Rewind to alert". Timeline scrolls to first event;
          | stepper resets to [Investigating •].

0:42–0:55 | Dependency graph: payments node pulses red; DB-primary node has
          | warning ring; arrow labeled "precedes by 4m 10s".
          | Tap DB-primary → popover shows live SQL:
          |  SELECT service, LAG(pool_used,1) OVER (PARTITION BY service
          |    ORDER BY ts) AS prev_used FROM metrics WHERE ts > now()-900
          | PRESENTER: "ClickHouse ran a lag/lead window function over every
          | service metric. The DB pool had been climbing for four minutes
          | before the first alert fired. Real SQL on a live metric stream.
          | Not an LLM guess."

0:55–1:10 | Log entry highlighted: "02:14:03 — severity extraction: P1".
          | Badge: "Pioneer / GLiNER2 — schema-conditioned — [measured]ms".
          | PRESENTER: "Severity and blast radius are extracted synchronously
          | at alert ingestion by a 300-million-parameter model with a custom
          | schema — severity P0 to P3, affected-services span extraction —
          | before any frontier-LLM call. [Speak the measured latency — do not fabricate a number.] GLiGuard,
          | its sibling safety model, screens every outbound message the agent
          | sends — that's what a guardrail model is actually for."

1:10–1:25 | Log entry: "02:14:07 — Senso runbook retrieval". Side panel shows
          | cited card: "Step 3: raise connection pool ceiling…
          | [Senso / payments-runbook-v4, updated 2026-05-01]".
          | PRESENTER: "Senso holds the institutional memory. The agent didn't
          | look up *a* runbook — it found the step that worked last time for
          | this exact symptom pattern, with the citation."

1:25–1:40 | ALT-TAB to Slack #incidents. Visible message:
          |  "SHERPA UPDATE — payments P1. Causal chain: DB pool exhaustion
          |   (02:09:51) → latency spike (02:14:01). Runbook step 3 in
          |   progress. Suggested owner: @dana-chen. Jira: PLAT-4417"
          | PRESENTER: "Composio posted this and opened the Jira ticket — two
          | apps, one OAuth grant, no copy-paste." ALT-TAB back.

1:40–1:55 | TAB 2: Langfuse trace waterfall (live data):
          |  GLiNER2 inference [measured]ms | Senso retrieval 312ms | ClickHouse causal
          |  SQL 204ms | postmortem draft (claude-fable-5) 6.8s $0.0041 |
          |  GLiGuard output-screen 92ms | SLACK_SEND 190ms | JIRA_CREATE 340ms
          | PRESENTER: "Every call instrumented via Langfuse — latency, token
          | cost, eval score. Total LLM spend for this incident response:
          | four-tenths of a cent."

1:55–2:10 | TAB 3: Airbyte connections — GitHub → ClickHouse and Jira →
          | ClickHouse, both green, "last sync 1h ago".
          | PRESENTER: "Ownership isn't a guess. Airbyte pulled 90 days of
          | GitHub and Jira history into ClickHouse. dana-chen resolved nine
          | of the last twelve payments incidents."

2:10–2:20 | Back to timeline; open Guild audit-log drawer:
          |  "Session INC-2026-0612-001 | Investigating → Mitigating → Resolved
          |   | Credential scope: Slack #incidents [r/w], Jira [create] |
          |   14 typed events, all persisted"
          | PRESENTER: "Guild manages the persistent session — every state
          | transition, every credential scope, append-only. The postmortem
          | didn't reconstruct anything. It read its own notes."

2:20–2:35 | Point to address bar: https://incidentsherpa.onrender.com
          | render.yaml popover: services: [webhook-api, agent-worker, frontend]
          | PRESENTER: "Three services in one Render Blueprint. The stack was
          | live twenty-five minutes into our build."

2:35–2:50 | Back to fully rendered postmortem.
          | PRESENTER: "Every line is traceable to a timestamp. No human wrote
          | it. No human had to remember anything at 2 AM. The only source of
          | truth for what happened during an incident is the system that was
          | actually watching."

2:50–3:00 | Full timeline view, RESOLVED badge, all steppers green.
          | PRESENTER: "IncidentSherpa. The incident commander that writes the
          | postmortem itself — because it was in the room." [Pause.]
```

### (b) Wow moment
**0:12–0:30** — postmortem streams live with the causal chain, named owner backed by 9-of-12 history, and a Jira reference, 18 seconds after one click. The judge sees the payoff before the mechanism; the rewind rewires comprehension backward.

### (c) Sponsor-visibility checklist

| Sponsor | Seconds | On-screen element |
|---|---|---|
| Guild.ai | 0:00–0:08, 2:10–2:20 | State-machine stepper from frame 1; audit-log drawer with session ID, credential scopes, 14 typed events |
| ClickHouse | 0:42–0:55, 1:40–1:55 | Live LAG/LEAD SQL popover; "ClickHouse causal SQL — 204ms" Langfuse row |
| Langfuse | 1:40–1:55 | Full trace waterfall, cost column, "$0.0041" spoken |
| Airbyte | 1:55–2:10 | Connector list, GitHub+Jira green, "via Airbyte Agent Engine" detail on hover |
| Senso.ai | 1:10–1:25 | Cited runbook card with "[Senso / payments-runbook-v4]" source tag |
| Composio | 1:25–1:40 | Live Slack message + Jira ticket badge |
| Pioneer | 0:55–1:10 | "Pioneer / GLiNER2 — [measured]ms" badge; schema-conditioned extraction + GLiGuard guardrail spoken |
| Render | 2:20–2:35 | onrender.com URL in address bar; render.yaml popover |
| OpenUI | entire | Timeline, dependency graph, streaming postmortem ARE the OpenUI component |

### (d) Fallbacks (cue → action)

| Dependency | Cue | Fallback |
|---|---|---|
| Guild SDK/REST | T+0:15 go/no-go fails | Single Python IncidentAgent; Guild session via REST; audit events POSTed; script unchanged. If REST also dead: LangGraph state, drop Guild prize claim only. |
| ClickHouse live insert | Rehearsal timeout | CSV pre-replayed before demo; causal SQL still executes live. "We're replaying a recorded incident at 10× speed." |
| Composio Slack | Auth error at 1:25 | Pre-recorded Slack screenshot tab: "posted during our setup run." |
| Composio Jira | No PLAT-4417 badge | Pre-seeded ticket in background tab. |
| Pioneer API | 402 or >500ms at T+0:15 | Run GLiNER2/GLiGuard locally via transformers (Apache 2.0); badge latency becomes ~400ms — "local inference, still sub-half-second." |
| OpenUI SSE | Stream stalls | Hidden static postmortem div revealed on F2. |
| Render cold start | No webhook response in 5s | /health warm-ping cron in render.yaml; else curl trigger from pre-typed terminal. |
| Airbyte status | Red connector at 1:55 | Bookmarked screenshot of green list: "last sync an hour ago." |
| Langfuse | Empty dashboard | Pre-taken waterfall screenshot. |

### (e) Pre-staging checklist
- **Accounts/OAuth:** Guild (SDK or REST descope tested E2E); ClickHouse Cloud (metrics/events/incident_sessions tables, CSV inserted); Langfuse (keys, test span); Airbyte (GitHub+Jira authorized, synced once, green); Senso (3 runbooks, 2 postmortems, ownership map: dana-chen→payments, alex-kim→db-primary); Composio (`link()` Slack chat:write + Jira create, both tested); Pioneer (GLiNER2 test call <200ms or local pipeline ready); Render (Blueprint deployed, 3 services green, /health 200).
- **Seeded data:** incident_metrics.csv crafted so LAG/LEAD names DB pool as 4m10s precursor; Guild session INC-2026-0612-001 with 14 typed events; ClickHouse events table matching the visible log; postmortem dry-run output saved as static fallback; PLAT-4417 pre-created; #incidents has one prior SHERPA message.
- **Tabs (pinned, in order):** 1 OpenUI timeline (mid-incident state), 2 Langfuse waterfall (filtered to session), 3 Airbyte connections, 4 Slack #incidents, 5 Jira PLAT-4417, 6 Render dashboard.
- **Terminals (background):** curl trigger pre-typed; CSV replay pre-typed.
- **Rehearsal gate:** 3 full runs; postmortem complete by 0:30 on all; ≥7 Langfuse rows; rewind <4s. Any Resolve-click failure → activate static fallback and re-rehearse.

---

## Demo script: ContractCopilot (Rev 2)

**Target runtime:** 3:00. **Station:** one laptop; tabs: Gmail (NDA email), OpenUI redline diff, Langfuse, ClickHouse console, Gmail Sent. Presenter mode 125%.

### (a) Timestamped beats

```
0:00–0:10 | SCREEN: Gmail inbox. One email: "Acme Corp — MSA for Review",
          | PDF attachment, "just now".
          | PRESENTER: "A vendor just sent us their standard MSA. Normally
          | this sits in a legal queue for three days. Watch what happens
          | when our agent picks it up."
          | CLICK email open. (Pipeline already running via Composio webhook;
          | OpenUI tab shows pulsing "Analyzing…" badge.)

0:10–0:20 | SWITCH to OpenUI tab. Status bar: "Extracting clauses… 6 found".
          | Live ClickHouse precedent results appear:
          |  "Liability Cap — precedent matches: 12 (accepted 9, rejected 3)"
          |  "Auto-Renewal — precedent matches: 7 (accepted 2, rejected 5)"
          | PRESENTER: "Composio detected the attachment the moment it landed.
          | Six clauses extracted. We've seen this exact liability cap
          | language twelve times before."

0:20–0:35 | First diff card streams token-by-token:
          |  LEFT (original): "Liability shall not exceed $10,000 or one
          |    month's fees, whichever is lesser."
          |  RIGHT (redline, highlights): "…the greater of $500,000 or twelve
          |    months' fees."
          |  RED badge "High risk — below policy minimum"
          |  "9 of 12 prior contracts accepted ≥$250k cap"
          |  "[Senso / legal-playbook-liability-v3]"
          |  [Accept] [Reject] [Escalate to Legal]
          | PRESENTER: "Liability cap of ten thousand dollars. Our Senso
          | playbook says minimum two-fifty. The redline is pre-drafted.
          | I haven't touched a keyboard."

0:35–0:42 | *** WOW MOMENT *** CLICK "Accept". Card flips green in <0.5s;
          | second card (auto-renewal) slides up automatically.
          | PRESENTER: "Accept. Done. One click."

0:42–0:58 | Second card: 90-day → 30-day notice redline, YELLOW badge,
          | "5 of 7 prior contracts negotiated to ≤30 days",
          | "[Senso / legal-playbook-renewal-v2]".
          | CLICK "Reject" → card flips orange "Queued for counter-proposal".
          | Counter-proposal preview slides in: To vendor@acmecorp.com,
          | "Re: MSA — Proposed Revisions", body with both dispositions,
          | attachment MSA_redlined.pdf.

0:58–1:10 | PRESENTER: "The counter-proposal is pre-written from Senso's
          | playbook language — our company's actual negotiating position
          | from our last seven renewals, not a generic LLM opinion."
          | CLICK "Queue for Send". Status: "Sending via Composio…"

1:10–1:20 | SWITCH to Gmail Sent. Top email: "Re: MSA — Proposed Revisions,
          | sent just now". Open it; body + attachment visible.
          | PRESENTER: "Sent. The loop is closed. Composio read the contract
          | from Gmail and sent the counter back through Gmail. Ironclad and
          | Spellbook give you a PDF report. This sends the email."

1:20–1:38 | TAB: Langfuse waterfall:
          |  GMAIL_FETCH (Composio) 340ms | pdfplumber 890ms | embedding +
          |  ClickHouse write 1.2s | precedent query 88ms | Senso liability
          |  290ms | TrueFoundry→cheap-model 1.1s $0.0008 | Senso renewal
          |  280ms | TrueFoundry→cheap-model 1.0s $0.0007 | GMAIL_SEND 410ms
          |  TOTAL: $0.0015 — 2 clauses redlined
          | PRESENTER: "Every call timed and costed. Two clauses for
          | fifteen-hundredths of a cent — TrueFoundry routed this 6-clause
          | NDA to a cheap model. A hundred-page MSA routes to a frontier
          | model. The routing rule is right there in the trace."

1:38–1:52 | CLICK TrueFoundry row → expanded routing decision:
          |  "clause_count: 6 → gpt-4o-mini; rule: ≤8 → cheap, >8 →
          |   claude-fable-5". Eval column: "redline_quality: 0.91".
          | PRESENTER: "Routing is live and auditable. The eval score
          | compares the redline against Senso's playbook answer — Langfuse
          | runs it automatically after every call."

1:52–2:05 | Back to OpenUI; open ClickHouse drawer:
          |  "clauses table — 58 rows (50 corpus + 8 this contract);
          |   accepted 47 / rejected 11; last write 42s ago"
          | Hover Liability Cap → SQL tooltip:
          |  SELECT COUNT(*) FROM clauses WHERE clause_type='liability_cap'
          |    AND accepted=true → 9
          | PRESENTER: "That's real columnar SQL a judge can read and verify.
          | Not a vector claim. The precedent count on the card is this number."

2:05–2:18 | Senso citation panel: two policy cards with acceptable ranges,
          | escalation triggers, source + last-updated dates.
          | PRESENTER: "Every redline is grounded in a Senso policy document.
          | The agent cannot invent a liability range. This is why it's not
          | Spellbook — the policy knowledge lives in your workspace, not in
          | the model weights."

2:18–2:30 | Address bar: https://redline.onrender.com. render.yaml mention.
          | Scroll shows green (accepted) and orange (queued) cards together.
          | PRESENTER: "Single Render Blueprint: webhook, worker, frontend.
          | Live twenty-five minutes into the build."

2:30–2:45 | TAB: ClickHouse console, pre-typed GROUP BY clause_type query.
          | CLICK Run → result table in 80ms (liability_cap 12/9,
          | auto_renewal 7/2, indemnification 6/5, …).
          | PRESENTER: "Live query. The acceptance history across the corpus.
          | The more contracts it processes, the better the precedent signal."

2:45–3:00 | Back to diff view: one green card, one orange, banner
          | "Counter-proposal sent via Composio — 1:10 ago."
          | PRESENTER: "An NDA landed in Gmail. Forty-five seconds later the
          | agent had read it, queried twelve months of precedent, grounded
          | every redline in our playbook, and sent the counter-proposal.
          | The lawyer's job is the one click to approve. Not the three days
          | to get there." [Pause.]
```

### (b) Wow moment
**0:35–0:42** — one click flips the liability redline to Accepted and the next card slides up automatically. The audience grasps that the entire workflow ran before any human action; one click = three days saved.

### (c) Sponsor-visibility checklist

| Sponsor | Seconds | On-screen element |
|---|---|---|
| Composio | 0:00–0:10, 1:10–1:20, 1:20–1:38 | Inbox detection; sent counter-proposal; GMAIL_FETCH/SEND rows in Langfuse |
| ClickHouse | 0:10–0:20, 1:52–2:05, 2:30–2:45 | Live precedent counts; SQL tooltip; live console query with 80ms result |
| Langfuse | 1:20–1:52 | Full waterfall, cost column, $0.0015 total, eval 0.91, routing row expansion |
| Senso.ai | 0:20–0:35, 2:05–2:18 | Source tags on diff cards; full policy cards with ranges + escalation triggers |
| TrueFoundry | 1:20–1:52 | Routed-model rows with costs; expanded clause-count routing rule |
| OpenUI | entire | The redline diff component IS the product UI |
| Render | 2:18–2:30 | onrender.com address bar; render.yaml Blueprint |

### (d) Fallbacks (cue → action)

| Dependency | Cue | Fallback |
|---|---|---|
| Composio Gmail webhook | No "Analyzing…" badge in 5s | Background 60s polling script already running; or CLI `python trigger.py --pdf edgar_nda.pdf` — "the webhook fires on arrival; for the demo I'll trigger manually." Composio stays load-bearing (OAuth + send). |
| Composio send | Sent folder empty at 1:10 | Show pre-created draft in Drafts: "queued for one-click send — the lawyer approves before anything goes" (the intended narrative anyway). |
| ClickHouse console | Run spins >5s | Pre-saved result screenshot tab; diff-card counts already corroborate. |
| Senso | Card without source tag | Static policy cards in hidden div, F2 reveal. |
| TrueFoundry | 429 / wrong model | `TRUEFOUNDRY_FALLBACK=True` direct cheap-model path; skip the 1:38 routing expansion. |
| pdfplumber | Status stuck on "Extracting…" | Eliminated by pre-staged EDGAR NDA; ultimate fallback `--clauses extracted_clauses.json`. |
| OpenUI SSE | Card stalls mid-stream | Hidden completed-card div, F2. |
| Render cold start | 502 on load | /health warm-ping cron; else local dev server. |
| Langfuse | No traces | Pre-taken waterfall screenshot. |

### (e) Pre-staging checklist
- **Accounts/OAuth:** Composio (`link()` gmail.readonly + gmail.send, tested send, webhook → Render); ClickHouse (clauses + redlines schemas); Langfuse (project REDLINE, redline_quality eval template); TrueFoundry (PAT, both routing branches tested + logged); Render (Blueprint green, /health 200, cold-start cron); Senso (6 policy docs, one per clause type, structured policy/range/escalation, cited responses verified).
- **Seeded data:** 50 synthetic historical clauses matching the script's numbers (liability 12/9, renewal 7/2, …); EDGAR NDA at demo_assets/edgar_nda.pdf (text layer confirmed, contains a <$250k liability cap + >30-day renewal clause); extracted_clauses.json fallback; counter-proposal email pre-tested to throwaway; fallback_cards.html; langfuse_waterfall.png.
- **Tabs (pinned, in order):** 1 Gmail inbox (unread Acme email on top), 2 OpenUI diff (pipeline pre-triggered 30s before recording), 3 Langfuse waterfall, 4 ClickHouse console (query pre-typed, not run), 5 Gmail Sent/Drafts.
- **Terminals (background):** trigger.py --pdf pre-typed; trigger.py --clauses pre-typed; composio_polling.py running.
- **Rehearsal gate:** 3 full runs with EDGAR NDA; trigger-to-first-card <15s; counter-proposal arrives <5s after Queue-for-Send; ≥9 Langfuse rows; live query <200ms. Any threshold miss → switch to that fallback path and re-rehearse before final recording.
