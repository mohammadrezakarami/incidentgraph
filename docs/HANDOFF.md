# IncidentGraph Handoff

Last updated: 2026-09-23

## Current phase

Phase 0 through Phase 6 are complete and passed. Phase 6 connects queue leases to PostgreSQL LangGraph checkpoints, adds fenced/idempotent publication, durable authenticated review resume, cooperative cancellation, and budgeted report-version follow-ups. It used no real model or paid service.

Roadmap position: Phase 6 of 11 delivery phases is complete; including Phase 0, 7 of 12 gates are complete and Phases 7–11 have not started.

## Last verified command

Executable verification of the current Phase 6 foundation:

```text
make lint
make typecheck
make test
make migrate
make test-phase6-integration
make verify-incident-eval
make investigator-status
```

Result: Ruff and strict mypy pass; 51 unit tests, 6 queue/recovery integration tests, and 4 deterministic checkpoint/coordinator tests pass. Recovery fences stale attempts, review waits release leases, a restarted process resumes from PostgreSQL, cancellation fails closed, and an explicitly budgeted follow-up publishes report version 2. The incident held-out split remains sealed and no model workload ran for Phase 6.

## Configuration assumptions

- Project root is `/Users/mohammadrezakarami/Documents/New project/incidentgraph`.
- The standalone local repository is initialized on branch `main`.
- Private remote `origin` is `https://github.com/mohammadrezakarami/incidentgraph.git`.
- Default backend runtime: Python 3.12 managed for the project with uv.
- Frontend runtime: Node 24.13.1 and npm 11.8.0.
- The default model provider remains disabled. The Phase 5 verification used the loopback-only local-compatible adapter in ephemeral Colab with a zero monetary ceiling; paid calls remain prohibited.
- Default local embedding candidate: `sentence-transformers/all-MiniLM-L6-v2`, with the exact Hub revision pinned during Phase 3.
- Active embedding revision: `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, 384 dimensions, CPU, batch size 16.
- Active corpus: `incidentgraph-lab-corpus-v1-466b7569b585`.
- Retrieval held-out seal: `a77524916562fdd4337e88d0efa295813fe05e0910d1a2bc1c51f9ff2d778c3c`.
- Incident held-out seal: `1dbac7ea0da7702ad13c387743c2c5c795e45f3d81c78d857a98095cf25d8b67`.
- Retrieval limits: vector 20, full-text 20, RRF k=60, graph depth 2, graph nodes 50, final chunks 8, final tokens 5,000.
- One worker and one active LLM investigation.
- Normal core container target: approximately 6.25 GiB aggregate; optional observability profiles off.
- No production data, external tracing, public endpoints, remediation, or paid calls.

## Open issues and honest limitations

1. Unit-only global coverage remains below the retained 85 percent later-core gate.
2. Phase 7 still needs the full production API/worker assembly and incident console; the default CLI worker remains the non-AI foundation worker.
3. Cooperative cancellation cannot undo a provider request or charge already issued before cancellation is observed.
4. GitHub CLI authentication is stale, although the private remote exists and normal Git push works.
5. No paid provider is allowed; the verified real-model path is free and local-compatible.
6. Phase 2 captures predate the curated corpus and need recapture before final as-of evaluation pairing.
7. The 37-document corpus and development sets are project-authored laboratory material; results are not held-out or production claims.
8. Both Phase 5 real-model reports were safely inconclusive after bounded structured-output failures. This passes the safety/integration gate but is not a diagnosis-quality claim.
9. Direct hybrid is slightly below vector on the development split; the current result is retained rather than tuned against held-out data.

## Next three tasks

1. Obtain explicit approval to start Phase 7.
2. Build the complete API and incident console on the Phase 6 durable coordinator.
3. Keep the incident held-out split sealed until the separately approved frozen Phase 9 evaluation.

## Relevant documents

- `docs/progress/phase-00-report.md`
- `docs/progress/phase-01-report.md`
- `docs/progress/phase-02-report.md`
- `docs/progress/phase-03-report.md`
- `docs/progress/phase-04-report.md`
- `docs/progress/phase-05-report.md`
- `docs/progress/phase-06-report.md`
- `docs/adr/0001-single-investigator.md`
- `docs/adr/0002-neo4j-graph-and-vectors.md`
- `docs/adr/0003-postgresql-durable-execution.md`
- `docs/adr/0004-replay-isolation.md`
- `docs/adr/0005-read-only-operational-scope.md`

## Resume procedure

Read this file, `docs/PROJECT_STATUS.md`, `docs/TASKS.md`, all phase reports, and all accepted ADRs. Compare the actual directory and Git state with this handoff. Do not repeat Phases 0–6 or rerun the completed real-model gate without a concrete need. Never make paid calls. Before any heavy local model download/run, explain the resource need and offer the Colab path. Keep the incident held-out split sealed.
