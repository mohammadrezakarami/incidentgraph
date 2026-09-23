# IncidentGraph Handoff

Last updated: 2026-09-23

## Current phase

Phase 0 through Phase 4 are complete and passed. Phase 5 is active: its deterministic/local foundation passes, while the mandatory real-model gate is blocked by the zero-cost constraint and absence of a local chat runtime/model.

Roadmap position: Phase 5 of 11 delivery phases is active; including Phase 0, 5 of 12 gates are complete, 1 is active, and 6 later phases have not started.

## Last verified command

Executable verification of the current Phase 5 foundation:

```text
make lint
make typecheck
make test
make migrate
make test-investigator-integration
make verify-incident-eval
make investigator-status
```

Result: Ruff and strict mypy pass; 41 unit tests and 2 Phase 5 integration tests pass. PostgreSQL persists checkpoints, full immutable evidence, and immutable reports while checkpoint state excludes raw telemetry. The incident dataset has 60 cases split 30/30; seal `1dbac7ea0da7702ad13c387743c2c5c795e45f3d81c78d857a98095cf25d8b67` passes and held-out remains unevaluated. Status truthfully reports the real-model gate as blocked.

## Configuration assumptions

- Project root is `/Users/mohammadrezakarami/Documents/New project/incidentgraph`.
- The standalone local repository is initialized on branch `main`.
- Private remote `origin` is `https://github.com/mohammadrezakarami/incidentgraph.git`.
- Default backend runtime: Python 3.12 managed for the project with uv.
- Frontend runtime: Node 24.13.1 and npm 11.8.0.
- Model provider is disabled, the monetary ceiling is zero, and paid calls are prohibited.
- Default local embedding candidate: `sentence-transformers/all-MiniLM-L6-v2`, with the exact Hub revision pinned during Phase 3.
- Active embedding revision: `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, 384 dimensions, CPU, batch size 16.
- Active corpus: `incidentgraph-lab-corpus-v1-466b7569b585`.
- Held-out seal: `a77524916562fdd4337e88d0efa295813fe05e0910d1a2bc1c51f9ff2d778c3c`.
- Retrieval limits: vector 20, full-text 20, RRF k=60, graph depth 2, graph nodes 50, final chunks 8, final tokens 5,000.
- One worker and one active LLM investigation.
- Normal core container target: approximately 6.25 GiB aggregate; optional observability profiles off.
- No production data, external tracing, public endpoints, remediation, or paid calls.

## Open issues and honest limitations

1. The deterministic investigator and grounded report path are implemented, but no real chat model has driven real tools yet.
2. Unit-only global coverage is 48.17 percent; the retained 85 percent later-core gate fails today.
3. Full durable review interrupt/resume semantics remain Phase 6 work; Phase 5 currently has only the lifecycle boundary.
4. GitHub CLI authentication is stale, although the private remote exists and normal Git push works.
5. No paid provider is allowed. A free local/Colab model run remains the only approved path to the real-model gate.
6. Phase 2 captures predate the curated corpus and need recapture before final as-of evaluation pairing.
7. The 37-document corpus and 20-question development set are project-authored laboratory material; development results are not held-out or production claims.
8. Direct hybrid is slightly below vector on the development split; the current result is retained rather than tuned against held-out data.

## Next three tasks

1. Select a free local or Colab chat model/runtime and document its resource needs before running it.
2. Run development-only real-model smoke cases that demonstrate adaptive real tool use; keep held-out sealed.
3. Close Phase 5 only if the real-model gate passes; otherwise retain the measured failure/blocker.

## Relevant documents

- `docs/progress/phase-00-report.md`
- `docs/progress/phase-01-report.md`
- `docs/progress/phase-02-report.md`
- `docs/progress/phase-03-report.md`
- `docs/progress/phase-04-report.md`
- `docs/progress/phase-05-report.md`
- `docs/adr/0001-single-investigator.md`
- `docs/adr/0002-neo4j-graph-and-vectors.md`
- `docs/adr/0003-postgresql-durable-execution.md`
- `docs/adr/0004-replay-isolation.md`
- `docs/adr/0005-read-only-operational-scope.md`

## Resume procedure

Read this file, `docs/PROJECT_STATUS.md`, `docs/TASKS.md`, all phase reports, and all accepted ADRs. Compare the actual directory and Git state with this handoff. Do not repeat Phase 0/1/2/3/4 or the completed deterministic Phase 5 foundation. Never make paid calls. Before any heavy local model download/run, explain the resource need and offer the Colab path. Keep the incident held-out split sealed.
