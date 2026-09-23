# Phase 7 Completion Report — API and Incident Console

Date: 2026-09-23

Status: **PASS**

Roadmap position: Phase 7 of 11 delivery phases is complete. Including discovery Phase 0, **8 of 12 gates are complete**.

## Scope and resource boundary

Phase 7 completed the production API/worker assembly and the React incident console. No model,
Ollama, GPU, held-out evaluation, or paid service ran. The verification workload was TypeScript
compilation, small unit tests, one bounded PostgreSQL contract case, prior-phase regression tests,
and one headless browser flow. The Playwright Chromium download was a one-time browser dependency,
not an AI model or runtime workload.

The browser gate intentionally uses a deterministic fixture publisher. It is visibly labeled in
the evidence and report limitations, publishes through the real queue lease and atomic report
publication contract, and is test evidence only. It is not presented as an AI-generated diagnosis
or benchmark result.

## Delivered API and worker contract

- Completed create, paginated list, record, report, evidence, review, cancellation, follow-up,
  authorized service catalog, time-aware dependencies, health, SSE, and operator metrics routes.
- Added server request IDs, bounded request bodies, pagination caps, per-principal local rate
  limits, UTC-aware timestamps, canonical service/alias resolution, idempotency, consistent error
  bodies, and retry hints.
- Enforced ownership on every investigation HTTP lookup and mutation, with a deliberate operator
  bypass. Cross-user records, reports, evidence, review, and streams fail closed.
- SSE uses the bearer header, never a query token. Persisted sequence numbers and
  `Last-Event-ID` resume strictly after the last displayed event. Heartbeats and a five-minute
  connection cap force periodic reauthentication.
- Added bounded tool/model-decision events with outcome, duration, reason, summary, and evidence
  references. Deduplication keys keep replay/recovery idempotent.
- Replaced the non-AI foundation worker entrypoint with the real `OpenAIInvestigatorModel`,
  `CaptureToolbox`, PostgreSQL checkpointer, and `DurableWorkflowCoordinator` assembly. A disabled
  or unavailable provider fails clearly; no fake provider is substituted.
- Added `docs/security/THREAT_MODEL.md` before treating the expanded surface as complete.

## Delivered incident console

- React 19, TypeScript, and Vite with exact npm locks and the Phase 0 Node/npm runtime contract.
- In-memory bearer authentication by default, with an explicit tab-session option; tokens are not
  placed in URLs.
- Authorized investigation history and creation with service, question, UTC-converted time range,
  and clear LIVE/REPLAY selection.
- All lifecycle states: queued, running, waiting for review, completed, inconclusive, failed, and
  cancelled.
- Authenticated fetch-stream timeline, automatic retry, manual reconnect, sequence deduplication,
  concise model/tool summaries, durations, and outcomes.
- API-backed reports with ranked hypotheses, contradictions, limitations, impact, recommendations,
  and actual clickable evidence IDs.
- Evidence dialog with provenance, timestamps, validity/snapshot metadata, limitations, safe text
  rendering, and SVG metric range charts.
- Lazy-loaded Cytoscape only for the bounded dependency view. The initial production JavaScript
  chunk is approximately 244 KB before gzip (approximately 76 KB gzip); the graph chunk loads only
  when needed.
- Review copy explicitly states that acceptance publishes a diagnosis only and executes no
  operational change. Cancellation and budgeted versioned follow-ups are also available.
- Responsive laptop/mobile layout, readable contrast, keyboard focus, loading, empty, partial,
  reconnect, and accessible error states.

## Requirements-to-test mapping

| Requirement | Executable evidence |
|---|---|
| Complete endpoint contract and normalized errors | `tests/unit/test_api.py` plus real `tests/integration/test_phase7_api.py` |
| Owner/operator enforcement and cross-user failure | Real PostgreSQL contract test and Playwright request with the second identity |
| SSE resume without duplicate events | Unit `Last-Event-ID` test, real API SSE test, and Playwright manual reconnect request assertion |
| Displayed facts originate from API data | Vitest API-fact rendering test and unique Playwright fixture strings served by FastAPI |
| Citations open the correct record | Playwright opens the report citation and asserts its exact source/provenance and metric chart |
| Refresh preserves selected state | Playwright reloads with the selected ID in the URL and tab-scoped token, then reloads the report |
| Mode and review meaning are clear | Playwright asserts REPLAY and the non-remediation review warning before accepting |
| Real backend investigation flow | Browser creates via FastAPI, PostgreSQL queues/leases/publishes/reviews/resumes, then fixture data is deleted |
| Earlier durability behavior is preserved | Six queue/recovery and four checkpoint/coordinator regression tests |
| No paid or heavy model work | E2E server config names a never-invoked local provider; fixture usage records zero model calls and zero cost |

## Gate evidence

Final commands and observed results:

```text
.venv/bin/ruff check src tests scripts
.venv/bin/mypy src/incidentgraph
.venv/bin/pytest -q tests/unit
npm --prefix frontend test
npm --prefix frontend run build
RUN_INTEGRATION=1 .venv/bin/pytest -q tests/integration/test_phase7_api.py
RUN_INTEGRATION=1 .venv/bin/pytest -q tests/integration/test_durable_queue.py
RUN_INVESTIGATOR_INTEGRATION=1 .venv/bin/pytest -q \
  tests/integration/test_phase5_investigator.py \
  -k "postgres_checkpointer or review_interrupt or queue_lease or budgeted_follow_up"
npm --prefix frontend run test:e2e
```

- Ruff: pass.
- Strict mypy over 22 source modules: pass.
- Python unit tests: 58 passed.
- Vitest: 3 passed across 2 files.
- Frontend production build: pass.
- Real FastAPI/PostgreSQL contract: 1 passed.
- Phase 6 queue/recovery regression: 6 passed.
- PostgreSQL checkpoint/coordinator regression: 4 selected and passed.
- Playwright real-browser flow: 1 passed in approximately 1.8 seconds.

## Honest limitations

- The local bearer-token scheme, in-process rate limiter, and loopback deployment are reviewed
  development controls, not enterprise identity or a public multi-tenant security boundary.
- Browser facts and durable execution are verified. The deterministic E2E fixture does not measure
  diagnosis quality; the separate Phase 5 real-model gate remains the model evidence.
- The console charts the first bounded metric series. Multi-series comparison and richer trace
  visualization are possible extensions, not hidden claims.
- Global unit-only coverage remains below the retained 85 percent later-core target.
- Correlated API/worker/model/tool tracing, redaction sampling, adversarial injection tests,
  dependency-outage behavior, retention verification, and measured resource profiles belong to
  Phase 8.
- Cancellation remains cooperative and cannot undo a provider request or charge already accepted.
- The held-out Phase 9 incident set remains sealed and unevaluated.

## Next phase

Phase 8 is the next unstarted phase and requires explicit user continuation. It will harden
observability and security without expanding the read-only product scope or using paid services.
