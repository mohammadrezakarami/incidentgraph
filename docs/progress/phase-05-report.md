# Phase 5 Completion Report — Adaptive Investigator and Grounded Reports

Date: 2026-09-23

Status: **COMPLETE — PASS**

## Delivered scope

- Implemented one typed LangGraph investigator with all 12 required lifecycle nodes.
- Added strict LangChain structured-output boundaries for planning, hypothesis revision, and report drafting.
- Added eight typed, read-only observation tools with authorization, cutoff, template, payload, novelty, and timeout bounds.
- Added deterministic model-call, token, zero-cost, tool-call, round, and active-runtime budgets.
- Added grounded report schemas, citation resolution, contradiction fields, safe abstention, and one bounded report-repair route.
- Added PostgreSQL LangGraph checkpointing and immutable evidence/report persistence. Raw telemetry is stored separately; checkpoints retain bounded summaries, hashes, provenance, and evidence IDs.
- Added bounded recovery from malformed local-model tool arguments and deterministic partial reports when reserved reporting capacity is unavailable.
- Made replay dependency observations hermetic by reading the immutable captured topology rather than requiring a live Neo4j service.
- Built and sealed 60 incident cases: 30 development and 30 held-out, each split containing 20 identifiable, 5 insufficient-evidence, and 5 healthy cases.
- Kept the held-out split unopened. Seal: `1dbac7ea0da7702ad13c387743c2c5c795e45f3d81c78d857a98095cf25d8b67`.

## Free real-model gate

The mandatory real-model run was executed on a free Google Colab GPU. No hosted model API or paid service was used.

- Provider: local OpenAI-compatible Ollama endpoint.
- Model: `qwen3:4b-instruct-2507-q4_K_M`.
- Model digest: `0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`.
- Model size: 2,497,293,803 bytes; 4.0B parameters; Q4_K_M GGUF.
- Ollama: 0.34.3.
- Python: 3.12.14.
- Monetary cost: exactly USD 0.
- Artifact: `artifacts/evaluation/phase5-real-local/gate-results.json`.

The artifact was independently revalidated after download: its gate result was recomputed from the runs, both reports passed the typed schema, every cited evidence ID belonged to the recorded case evidence, persistence completed, cost remained zero, and the before/after held-out seals were identical.

## Gate results

| Check | Result |
|---|---|
| Two real development cases | PASS |
| Real model calls recorded | PASS |
| At least two real diagnostic tool executions per case | PASS |
| Evidence-driven second tools differ | PASS |
| Grounded observations recorded | PASS |
| Reports typed and citation-valid | PASS |
| PostgreSQL checkpoint completion | PASS |
| Zero monetary cost | PASS |

Observed bounded paths:

- `incident-dev-001`: `get_metrics → get_metrics`; 3 evidence items, 9 model calls, 4 total tool calls.
- `incident-dev-009`: `get_metrics → get_dependencies → get_metrics`; 3 evidence items, 9 model calls, 5 total tool calls.

Both final reports correctly remained `inconclusive`. The local model produced malformed tool arguments once and later returned structured-output request errors while drafting. The workflow did not invent a cause or exceed its budget: it retained collected evidence, emitted a deterministic citation-valid partial report, persisted the result, and recorded the failures. The Phase 5 gate therefore proves bounded adaptive execution and safe failure behavior; it does not claim diagnosis accuracy or production readiness.

## Verification

```text
ruff check .
mypy
pytest -m "not integration"
make test-investigator-integration
make verify-incident-eval
incidentgraph-investigator status
```

Observed deterministic results at closure:

- Ruff: pass.
- Strict mypy: pass.
- Unit tests: 45 passed; integration tests excluded from this count.
- Global unit-only coverage: 48.67%; the retained 85% later-core target remains open.
- Phase 5 PostgreSQL/capture integration tests: 2 passed.
- Incident manifest: 60 total, 30 development, 30 held-out; seal verified; held-out not evaluated.
- Real-model gate: 8/8 checks passed.
- Paid calls: none.

The repository-wide 85% coverage target remains a later-core release gate and is not weakened by this phase result.

## Decision

Phase 5 is complete. Including discovery Phase 0, **6 of 12 phase gates are complete**. Phase 6 is the next unstarted phase and requires explicit continuation before implementation begins.
