# IncidentGraph Handoff

Last updated: 2026-09-28

## Current phase

Latest steering: the user explicitly wants the Phase 9 quality problems fixed. Repair-2's returned
free-Colab probe was 7/10 and exposed unsafe over-abstention and false rationales. Repair-3 now uses
a trusted, service-scoped bounded policy and generated evidence templates; its consumed eleven-case
development replay is 11/11 with zero model/paid calls, including the reconstructed
healthy-high-traffic control. Details and immutable artifacts are in
`docs/progress/phase-09-repair.md`. Keep working on Phase 9; this does not authorize treating the
quality work as finished.

Phase 0 through Phase 8 are complete and passed. Phase 9 is also complete, but its immutable v1 and
separately frozen fresh v3 quality gates are both **FAIL**. The v3 free-Colab execution completed all
120 jobs, reproduced byte-for-byte locally, and received a written review over 20 actual reports.

Roadmap position: Phases 0–8 PASS; Phase 9 COMPLETE/FAIL; Phases 10–11 are not started.

## Last verified command

Current repair verification:

```text
.venv/bin/ruff check .
.venv/bin/mypy
.venv/bin/pytest -q -m "not integration"
.venv/bin/python -m incidentgraph.phase9_repair \
  --output-dir artifacts/evaluation/phase9-repair3-development
```

Result: strict mypy passes; all 121 selected non-integration tests pass. The targeted repair suite
passes 38 tests. Repair-3 produces 11/11 valid, deterministically supported development reports
with 11/11 label match, zero model calls and USD 0. Ruff passes after excluding the intentionally
Colab-specific repair notebook consistently with the existing Colab notebook exclusions. `make
lint` and `make typecheck` could not rebuild through uv in the restricted shell because PyPI DNS
was unavailable; direct commands using the existing locked environment passed.

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
11. Phase 9 v3 fixed the v1 latency and policy-violation failures but still failed diagnosis,
    abstention, citation-validity, claim-support, and coverage targets.

## Next three tasks

1. Integrate the repair-3 policy and derived evidence path into a new workflow without modifying
   frozen v1/v2/v3 files; add end-to-end workflow checks. The omitted healthy-high-traffic
   development capture is now included by deterministic reconstruction.
2. Raise whole-project core coverage to the retained 85% target, then define and seal a genuinely
   fresh evaluation set. Never relabel the consumed v3 set as independent held-out data.
3. Keep any model-heavy fresh run free and off the laptop. Do not launch another 120-job run until
   the new workflow, full development scope, freeze manifest and human-review rubric are ready.

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
