# IncidentGraph Handoff

Last updated: 2026-09-28

## Current phase

Latest steering: the user explicitly wants the Phase 9 quality problems fixed. Repair-3 now uses a
trusted, service-scoped bounded policy and generated evidence templates. It is integrated into v4,
145 non-integration tests pass, branch-aware core coverage is 85.14%, and a fresh 30-case held-out
set from 11 new post-repair captures is sealed. Freeze verification passes at bundle revision
`f3d990672a31ae606adbaec1f2abee745e1cc4b4`. The only remaining work is the free-Colab v4 run and
the written claim-support review after its ZIP returns. Details are in
`docs/progress/phase-09-repair.md`.

Phase 0 through Phase 8 are complete and passed. Phase 9 is also complete, but its immutable v1 and
separately frozen fresh v3 quality gates are both **FAIL**. The v3 free-Colab execution completed all
120 jobs, reproduced byte-for-byte locally, and received a written review over 20 actual reports.

Roadmap position: Phases 0–8 PASS; Phase 9 COMPLETE/FAIL; Phases 10–11 are not started.

## Last verified command

Current v4 repair verification:

```text
.venv/bin/ruff check .
.venv/bin/mypy
.venv/bin/pytest -q -m "not integration"
.venv/bin/python -m incidentgraph.phase9_v4_dataset verify
.venv/bin/python -m incidentgraph.phase9_v4_runner verify-freeze
```

Result: Ruff and strict mypy pass; 145 selected non-integration tests pass. The exact retained core
coverage command passes at 85.14%. The new held-out seal digest is
`b36dc01092ddc22565f061a4401b6710b9e77a46e5a10f3efc4a78058f23435d`; freeze verification covers
28 files/manifests. The v4 bundle SHA-256 is
`c31bb3a80b83ae2482eedd8364d3cfd2f3a9f60931dd10f263f2ee2bccb2c03f`. Use only
`phase9_v4_colab.ipynb` and `incidentgraph-phase9-v4-colab.bundle` for the next run.

Previous executable verification of the completed Phase 9 v3 result:

Executable verification of the completed Phase 9 v3 result:

```text
make lint
make typecheck
.venv/bin/pytest -m "not integration" --cov --cov-report=term
make verify-phase9-v3-freeze
.venv/bin/python scripts/complete_phase9_v3_manual_review.py \
  artifacts/evaluation/phase9-v3-fresh \
  --source-archive /Users/mohammadrezakarami/Desktop/phase9-v3-progress.zip
```

Result: Ruff and strict mypy pass; all 83 selected non-integration tests pass; coverage is 48.38%
and therefore correctly fails the retained 85% threshold. All 22 fresh captures, the 60-case v3
fixture, and the 37-file freeze verify. The 120-job free-Colab result reproduced byte-for-byte and
estimated paid cost remains USD 0.

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

1. Historical whole-package v3 coverage was below 85%; the newly explicit core runtime scope now
   passes at 85.14%. Do not present that scoped result as whole-repository coverage.
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
11. Phase 9 v3 fixed the v1 latency and policy-violation failures but still failed diagnosis,
    abstention, citation-validity, claim-support, and coverage targets.

## Next three tasks

1. Run every cell in `phase9_v4_colab.ipynb` with
   `incidentgraph-phase9-v4-colab.bundle` on a free T4 and return `phase9-v4-progress.zip`.
2. Reproduce the aggregate from the 120 returned job records and write the claim-support rubric
   over at least 20 fresh adaptive reports without changing any frozen input or target.
3. Publish the final v4 PASS/FAIL status honestly; only then decide whether Phase 9 closes and Phase
   10 may start.

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
Compare the actual directory and Git state with this handoff. Do not recreate the v3 dataset or
rerun its completed shards. Never make paid calls. Do not alter
any file hashed by `config/phase9-freeze-v1.json`, `config/phase9-v2-regression-freeze.json`, or
`config/phase9-v3-fresh-freeze.json`.
