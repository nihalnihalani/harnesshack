# No-Mock Audit — IncidentSherpa (Phase 8, preliminary)

Date: 2026-06-13. This is the preliminary adversarial sweep required by
build-loop.md ("triaged to zero unexplained hits"); the final Phase 9 re-run
happens after the three production E2E runs.

## Command and raw count

```
$ grep -rniE 'mock|stub|fake|lorem|TODO|FIXME' \
    --exclude-dir={node_modules,.git,.venv,.next} .
64 hits across 28 files
```

Notable zeros: **0 `TODO`, 0 `FIXME`, 0 `lorem`** anywhere in the tree, and
0 hits in `scripts/`, `demo_assets/`, `render.yaml`, or CI config.

## Triage — every hit accounted for, 0 needing a fix

### Category 1 — war-room / process prose (10 hits): LEGITIMATE

| Where | Why the word appears |
|---|---|
| `build-loop.md` (8 hits) | The loop prompt that *states* the no-mock rule ("NO MOCKS, NO STUBS, NO FAKE PATHS", "never idle, never stub", the Phase 8/9 audit instructions themselves — including the exact grep this document runs). |
| `ideas.md:27` | Rev 2.x planning prose for a *different, rejected* idea ("S3/mock source" in an Airbyte capability description). Decision record; not code. |
| `debate-log.md:30` | Devil's-advocate scoring prose ("Senso KB is fake seeded data") arguing *against* an idea — the debate record that produced the no-faking principle. |

War-room artifacts are immutable decision records (per task rules they are
never modified); the words there describe rules and rejected options.

### Category 2 — anti-mock guarantees in source comments/docstrings (25 hits): LEGITIMATE

Every hit in `libs/` and `apps/` is prose *promising the absence* of mocks —
the NotConfiguredError machinery that CLAUDE.md and BUILD-STATE.md mandate:

- `libs/errors.py:5`, `libs/__init__.py:5`, `libs/clickhouse/__init__.py:4` —
  "raise loudly instead of … returning fake data", "No fake writes".
- `libs/airbyte/__init__.py:3,26` — "Honest unconfigured state, NOT a mock:
  raises NotConfiguredError"; the error message itself says "no fake client
  is ever returned".
- `libs/pioneer/{gliner2.py:9, gliguard.py:10, __init__.py:10}`,
  `libs/senso/retrieve.py:10`, `libs/guild/{session.py:14-15, __init__.py:6}`,
  `libs/guild/descope.md:34,53` — per-client "never returns fake X on any
  path" guarantees (descope.md: "Do not silently fake an audit trail").
- `libs/composio_actions/send.py:26,164` — choke point "never fakes a send
  result"; the dedupe marker is explicitly labelled "nothing was sent,
  nothing is faked".
- `apps/api/main.py:12`, `apps/worker/postmortem.py:24,27,29,169,454`,
  `apps/worker/agent.py:28,122,446` — "No mocks, no fake 'ok'", "honest
  empty — never faked", "an empty fallback would be a fake artifact",
  "NOT silence, NOT fake tickets".
- `apps/frontend/src/components/causal-graph.tsx:7` — "No data -> an honest
  waiting state, never a fake graph."

These comments are load-bearing documentation of the honest-failure design;
removing the words would weaken the codebase, not strengthen it.

### Category 3 — test-isolation seams in tests/ (28 hits): LEGITIMATE

Two sub-kinds, both confined to `tests/`:

1. **Docstrings declaring the no-mock posture** (`tests/conftest.py:3`,
   `test_api.py:3,137`, `test_trigger.py:4,58`, `test_replay.py:3`,
   `test_resilience.py:5`, `test_choke_point.py:5`,
   `test_agent_pipeline.py:4`, `test_postmortem.py:4`,
   `test_webhook_security.py:3`) — e.g. "External services are NOT mocked.
   Tests control the ENVIRONMENT."

2. **`FakeExtraction` / `FakeEdge` injection values**
   (`test_agent_pipeline.py:45,53,93,94,254`, `test_postmortem.py:55,82,97,
   100,104,110,137,218`, `test_api.py:123,129,155,156`). These are plain
   data objects passed through `IncidentAgent`'s / `generate_postmortem`'s
   *constructor-injection seams* — a design documented in the production
   docstrings ("Test isolation (NOT runtime mocks): … every default is the
   real client"). No production module is patched at runtime; no
   `unittest.mock` import exists anywhere in the repo (verified:
   `grep -rn "unittest.mock\|MagicMock\|patch(" tests/ libs/ apps/ --include="*.py"`
   returns nothing). The classes are honestly *named* Fake because they are
   test inputs, which is exactly what makes this grep find them.

### Needs-fix findings

**None.** 64/64 hits triaged legitimate; nothing was changed to "pass" the
audit.

## Standing rule

Any future hit added to apps/, libs/, or scripts/ that is not (a) an
anti-mock guarantee in prose or (b) a constructor-injected test input in
tests/ is a regression: fix it before commit, then update this document.
