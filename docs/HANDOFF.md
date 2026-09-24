# IncidentGraph Handoff

Last updated: 2026-09-24

## Current phase

Phase 0 through Phase 8 are complete and passed. Phase 9 is frozen and in progress: its exact datasets, seals, code, prompts, model digest, corpus, scoring, targets, and zero-cost budget verify, while the heavy free-Colab run and manual review remain pending.

Roadmap position: Phase 8 of 11 delivery phases is complete; including Phase 0, 9 of 12 gates are complete. Phase 9 is not yet passed, and Phases 10–11 have not started.

## Last verified command

Executable verification of the current Phase 9 preparation surface:

```text
make lint
make typecheck
.venv/bin/pytest -m "not integration" -q
make verify-phase9-freeze
```

Result: Ruff and strict mypy pass; 65 Python unit tests pass with 18 integrations deselected. All 13 frozen files, the incident seal, and the retrieval seal match. No held-out result, local model run, GPU workload, or paid call was made during preparation.

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
- Optional local JSONL tracing defaults off. When enabled it writes redacted, rotating files under `data/runtime/app-traces`; no external exporter is configured.
- No production data, external tracing, public endpoints, remediation, or paid calls.

## Open issues and honest limitations

1. Unit-only global coverage remains below the retained 85 percent later-core gate.
2. Local JSONL tracing is not a centralized or multi-host observability backend; public deployment remains out of scope.
3. Cooperative cancellation cannot undo a provider request or charge already issued before cancellation is observed.
4. GitHub CLI authentication is stale, although the private remote exists and normal Git push works.
5. No paid provider is allowed; the verified real-model path is free and local-compatible.
6. Phase 2 captures predate most curated-corpus validity windows. Phase 9 records this before running and will not rewrite the sealed dataset; a future post-corpus capture set must receive a new version and seal.
7. The 37-document corpus and development sets are project-authored laboratory material; results are not held-out or production claims.
8. Both Phase 5 real-model reports were safely inconclusive after bounded structured-output failures. This passes the safety/integration gate but is not a diagnosis-quality claim.
9. Direct hybrid is slightly below vector on the development split; the current result is retained rather than tuned against held-out data.
10. The existing untracked `.env` predates Phase 7 service scoping. Add an explicit non-empty `service_ids` list to each configured principal before using the interactive console; missing scope fails closed and `make doctor` reports it without exposing secrets.

## Next three tasks

1. Upload `incidentgraph-phase9-colab.bundle` to `phase9_colab.ipynb` and run shards 0–11 on a free T4, carrying `phase9-progress.zip` between sessions.
2. Return the final archive, reproduce aggregates, and complete the required 20-report support rubric.
3. Publish honest PASS/FAIL target results and error analysis; do not start Phase 10 until the Phase 9 gate is decided.

## Relevant documents

- `docs/progress/phase-00-report.md`
- `docs/progress/phase-01-report.md`
- `docs/progress/phase-02-report.md`
- `docs/progress/phase-03-report.md`
- `docs/progress/phase-04-report.md`
- `docs/progress/phase-05-report.md`
- `docs/progress/phase-06-report.md`
- `docs/progress/phase-07-report.md`
- `docs/progress/phase-08-report.md`
- `docs/progress/phase-09-report.md`
- `docs/operations/OBSERVABILITY.md`
- `docs/security/SECURITY_TESTS.md`
- `docs/adr/0001-single-investigator.md`
- `docs/adr/0002-neo4j-graph-and-vectors.md`
- `docs/adr/0003-postgresql-durable-execution.md`
- `docs/adr/0004-replay-isolation.md`
- `docs/adr/0005-read-only-operational-scope.md`

## Resume procedure

Read this file, `docs/PROJECT_STATUS.md`, `docs/TASKS.md`, all phase reports, and all accepted ADRs. Compare the actual directory and Git state with this handoff. Do not repeat Phases 0–8 or rerun the completed real-model gate without a concrete need. Never make paid calls. Do not alter any file hashed by `config/phase9-freeze-v1.json`; run the heavy workload only through the resumable free-Colab path.
