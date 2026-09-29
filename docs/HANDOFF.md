# IncidentGraph Handoff

Last updated: 2026-09-29

## Current phase

Phase 10 is complete. The local-first release now has CI/security workflows, a common backend image
configuration, standard/low resource profiles, a generated secret-safe `.env`, an offline test
gate, PostgreSQL backup/restore, graceful worker shutdown, and a full operations runbook. The
isolated clean clone passed setup, 150 backend tests, 3 frontend tests, the production build, 8
enabled integration tests, 1 real API/browser demo, frozen v4 replay, backup/restore, and safe
teardown at USD 0. Details are in `docs/progress/phase-10-report.md`.

Phase 0 through Phase 10 are complete and passed. Phase 9's immutable v1 and separately frozen
fresh v3 quality gates remain historical **FAIL** results; the independently versioned v4 repair
is the final **PASS** result.

Roadmap position: Phases 0–10 PASS; Phase 11 is not started.

## Last verified command

Current Phase 10 release verification:

```text
make release-verify
make test-offline
make evaluate-test
make report
```

Result: release contract and Compose render pass; 150 offline backend tests, 3 frontend tests, and
the production build pass. In an isolated clean clone, the low-resource core, 4 migrations,
PostgreSQL/Neo4j smoke, 8 enabled integration tests, 1 Playwright demo, frozen v4 replay,
backup/restore, and safe teardown all pass.

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
12. Phase 9 v4 passes the frozen laboratory gate, but it is not production evidence: 30 cases share
    11 captures, the model controls only observation order, and the written review is AI-assisted
    rather than independent human validation.

## Next three tasks

1. Begin Phase 11 portfolio handoff and technical defense only when the user requests it.
2. Obtain separate approval before pushing Phase 10, which would trigger private-repository CI.
3. Preserve all Phase 9 frozen evidence and keep heavy model evaluation off the laptop.

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
- `docs/progress/phase-10-report.md`
- `docs/operations/RELEASE.md`
- `docs/operations/OBSERVABILITY.md`
- `docs/security/SECURITY_TESTS.md`
- `docs/adr/0001-single-investigator.md`
- `docs/adr/0002-neo4j-graph-and-vectors.md`
- `docs/adr/0003-postgresql-durable-execution.md`
- `docs/adr/0004-replay-isolation.md`
- `docs/adr/0005-read-only-operational-scope.md`

## Resume procedure

Read this file, `docs/PROJECT_STATUS.md`, `docs/TASKS.md`, the Phase 9 report, and the accepted ADRs.
Compare the actual directory and Git state with this handoff. Do not recreate the v3/v4 datasets or
rerun their completed shards. Never make paid calls. Do not alter
any file hashed by `config/phase9-freeze-v1.json`, `config/phase9-v2-regression-freeze.json`, or
`config/phase9-v3-fresh-freeze.json`; preserve the v4 freeze and evidence as well.
