# IncidentGraph Handoff

Last updated: 2026-09-28

## Current phase

Phase 0 through Phase 8 are complete and passed. The immutable Phase 9 v1 execution is complete and
its frozen quality gate is **FAIL**. A separately versioned v3 iteration now has fresh post-corpus
captures, a new held-out seal, frozen code/data/model settings, and a resumable free-Colab run plan.
The v3 model run has not started, so no v3 held-out quality result is claimed yet.

Roadmap position: Phases 0–8 PASS; Phase 9 v1 FAIL is retained; Phase 9 v3 is awaiting Colab;
Phases 10–11 are not started.

## Last verified command

Executable verification of the Phase 9 v3 sealed pre-run surface:

```text
make lint
make typecheck
.venv/bin/pytest -m "not integration" -q
.venv/bin/python -m incidentgraph.phase9_v3_dataset verify
make verify-phase9-v3-freeze
```

Result: Ruff and strict mypy pass; 83 unit tests pass; all 22 fresh captures pass executable
verification; the 60-case v3 fixture and 37-file evaluation freeze verify. The heavy v3 model run is
reserved for free Colab and estimated paid cost remains USD 0.

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
6. Phase 2 captures predate most curated-corpus validity windows in v1. The v3 dataset resolves this
   with a new post-corpus capture set and seal rather than altering v1.
7. The 37-document corpus and development sets are project-authored laboratory material; results are not held-out or production claims.
8. Both Phase 5 real-model reports were safely inconclusive after bounded structured-output failures. This passes the safety/integration gate but is not a diagnosis-quality claim.
9. Direct hybrid is slightly below vector on the development split; the current result is retained rather than tuned against held-out data.
10. The existing untracked `.env` predates Phase 7 service scoping. Add an explicit non-empty `service_ids` list to each configured principal before using the interactive console; missing scope fails closed and `make doctor` reports it without exposing secrets.
11. Phase 9 v1 failed diagnosis, citation-validity, policy-violation, latency, claim-support, and
    coverage targets. The v3 result remains unknown until its Colab archive is returned.

## Next three tasks

1. Run `phase9_v3_colab.ipynb` against `incidentgraph-phase9-v3-colab.bundle` on a free T4 and return
   the latest `phase9-v3-progress.zip` until 120/120 jobs complete.
2. Reproduce the returned aggregate locally and complete the written support rubric over at least 20
   reports without tuning against the opened v3 held-out answers.
3. Publish the final Phase 9 v3 report and only then decide whether Phase 10 may begin.

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

Read this file, `docs/PROJECT_STATUS.md`, `docs/TASKS.md`, the Phase 9 report, and the accepted ADRs.
Compare the actual directory and Git state with this handoff. Resume from the returned v3 progress
archive; do not recreate the dataset or rerun completed shards. Never make paid calls. Do not alter
any file hashed by `config/phase9-freeze-v1.json`, `config/phase9-v2-regression-freeze.json`, or
`config/phase9-v3-fresh-freeze.json`.
