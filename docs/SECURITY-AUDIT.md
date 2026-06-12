# Security Audit — IncidentSherpa (Phase 8 hardening)

Date: 2026-06-13. Auditor: automated hardening pass (credential-free portion).
Scope: Python dependency audit (`pip-audit`), frontend dependency audit
(`npm audit --omit=dev`), full-git-history secrets sweep, `.env` hygiene.
Every command output below is real and was produced against commit `1cd11cd`
(post-upgrade re-runs included).

## Summary

| Area | Findings | Fixed | Accepted (triaged) |
|---|---|---|---|
| pip-audit (Python venv) | 4 (all in `pip` itself) | 4 (pip 25.3 → 26.1.2) | 0 |
| npm audit (frontend, prod deps) | 26 advisories / 8 root packages | 20 (next 16.1.6 → 16.2.9) | 6 moderate (2 roots, below) |
| Secrets in git history | 0 | — | — |
| `.env` hygiene | clean (never committed, gitignored) | — | — |

## 1. Python — `pip-audit`

Initial run (`.venv/bin/pip-audit`, pip-audit 2.10.1):

```
Found 4 known vulnerabilities in 1 package
Name Version ID             Fix Versions
---- ------- -------------- ------------
pip  25.3    PYSEC-2026-196 26.1.2
pip  25.3    CVE-2026-1703  26.0
pip  25.3    CVE-2026-3219  26.1
pip  25.3    CVE-2026-6357  26.1
```

All four findings are in `pip` itself (the installer, not a runtime
dependency of any service). Fixed by upgrading the venv's pip to 26.1.2.
Re-run after the upgrade:

```
$ .venv/bin/pip-audit
No known vulnerabilities found
```

Zero findings in the actual runtime dependency set (fastapi, uvicorn,
pydantic, clickhouse-connect, langfuse, httpx, composio, anthropic).
Note for Phase 7: Render builds its own environment from
`apps/*/requirements.txt` with its own pip; re-run `pip-audit` in CI is a
reasonable follow-up but the dependency set itself is clean.

## 2. Frontend — `npm audit --omit=dev`

Initial run (next@16.1.6): **6 vulnerabilities reported by the summary
line (1 high), spanning 26 advisories across 8 flagged package ranges** —
20 advisories against `next` itself (HTTP request smuggling GHSA-ggv3-7p47-pfv8,
multiple middleware/proxy bypasses, RSC cache poisoning, image-API DoS,
Server-Action CSRF bypass, XSS via CSP nonces, and more), plus `postcss`
(bundled inside next) and the `prismjs → refractor → react-syntax-highlighter
→ @openuidev/react-ui` chain.

### Fixed

`next` upgraded 16.1.6 → **16.2.9** (commit `1cd11cd`); `npm run build`
verified clean on the new version. This cleared every direct Next.js
advisory.

### Accepted after triage (re-run output, next@16.2.9)

```
# npm audit report

postcss  <8.5.10
Severity: moderate
PostCSS has XSS via Unescaped </style> in its CSS Stringify Output - GHSA-qx2v-qp2m-jg93
fix available via `npm audit fix --force`
Will install next@9.3.3, which is a breaking change
node_modules/next/node_modules/postcss
  next  9.3.4-canary.0 - 16.3.0-canary.5

prismjs  <1.30.0
Severity: moderate
PrismJS DOM Clobbering vulnerability - GHSA-x7hr-w5r2-h6wg
No fix available
node_modules/refractor/node_modules/prismjs
  refractor  <=4.6.0
    react-syntax-highlighter  6.0.0 - 15.6.6
      @openuidev/react-ui  *

6 moderate severity vulnerabilities
```

**Finding A — postcss <8.5.10 (moderate, GHSA-qx2v-qp2m-jg93). ACCEPTED.**
- The vulnerable copy is the one *vendored inside next* (`node_modules/next/
  node_modules/postcss`), pinned by the Next.js team; even the newest next
  16.x ships it, and npm's only proposed "fix" is downgrading to next@9.3.3 —
  a nonsensical breaking downgrade that would reintroduce the 20 advisories
  fixed above.
- Exploitability: the advisory concerns XSS via unescaped `</style>` when
  stringifying *untrusted CSS input*. In this app postcss runs at **build
  time only**, on our own first-party CSS. No untrusted CSS ever reaches it.
- Mitigation: none needed beyond the above; revisit when Next.js bumps its
  vendored postcss.

**Finding B — prismjs <1.30.0 (moderate, GHSA-x7hr-w5r2-h6wg), via
refractor ≤4.6.0 ← react-syntax-highlighter ≤15.6.6 ← @openuidev/react-ui.
ACCEPTED.**
- `npm audit` reports **no fix available** anywhere in the chain; the chain
  is pulled in by `@openuidev/react-ui`, the sponsor UI kit that CLAUDE.md
  mandates for the frontend (OpenUI is a load-bearing integration).
- Exploitability: DOM clobbering requires an attacker who can already inject
  named DOM elements (e.g. `<img name=...>`) into the same document before
  Prism runs. This frontend renders only React-escaped text from our own
  API — typed events and a GLiGuard-screened postmortem — and never injects
  third-party HTML (`dangerouslySetInnerHTML` is not used; verified by grep
  over `apps/frontend/src`). There is no attacker-controlled markup surface.
- Forcing `prismjs@1.30` via npm `overrides` was considered and rejected:
  refractor 4.x is version-coupled to prismjs internals (language
  registration), and silently breaking the sponsor UI kit's syntax
  highlighting is a worse outcome than a non-reachable moderate advisory.
- Revisit when @openuidev/react-ui bumps react-syntax-highlighter/refractor.

## 3. Secrets audit — full git history

Sweep for credential-shaped assignments across every patch ever committed
(single branch `main`; `git branch -a` shows no others):

```
$ git log -p | grep -inE '(api[_-]?key|secret|token|password)\s*[:=]\s*[A-Za-z0-9_\-]{16,}'
(no output — 0 matches across 24,559 patch lines)
```

`.env` hygiene:

```
$ git log --all --oneline -- .env
(no output — .env has never entered history)

$ git check-ignore .env
.env            ← exit 0: ignored

$ git ls-files | grep -i "\.env"
.env.example    ← the only tracked env file
```

Result: **no secrets in history; `.env` never committed and is gitignored.**
The only tracked credential-related file is `.env.example`: 14 of its 17
slots are empty placeholders and the 3 populated ones are non-secret
defaults (`LANGFUSE_HOST`, `NEXT_PUBLIC_API_BASE`, `RATE_LIMIT_PER_MINUTE`)
— verified by `grep -E "^[A-Z_]+=.+" .env.example`.

## 4. Standing rules

- Secrets live only in `.env` (local) and Render env groups (deploy);
  `render.yaml` references groups by name and contains no values.
- `WEBHOOK_AUTH_TOKEN` (Phase 8) gates POST /trigger and /incidents/*;
  unset ⇒ a loud structured startup warning, never silence.
- Re-run this document's commands after any dependency change; update the
  triage table rather than letting accepted findings go stale.
