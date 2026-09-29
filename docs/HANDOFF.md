# IncidentGraph handoff

Last updated: 2026-09-29

## Current state

All **12 of 12** gated phases (Phase 0 through Phase 11) are complete and PASS at the defined local
portfolio scope. The final portfolio decision is in `docs/portfolio/FINAL_READINESS.md`, and the
Phase 11 evidence is in `docs/progress/phase-11-report.md`.

Historical Phase 9 v1 and v3 quality gates remain immutable FAIL results. The separately frozen v4
post-repair evaluation is the final PASS result: 120/120 jobs, all 9 frozen targets, 20 reviewed
reports, 69/69 supported atomic claims, 85.14% branch-aware core coverage, and estimated paid cost
USD 0. The review is AI-assisted, not independent human validation; 30 variants share 11 captures;
the local model controls observation order while trusted code owns the synthetic-lab diagnosis and
citations.

Phase 11 adds a final technical report, timed demo, repository-native diagrams, three sanitized
real-flow screenshots, five CV bullets mapped to evidence, a 12-question technical-defense guide,
and an explicit portfolio-versus-production readiness decision.

## Last verified commands

```text
make portfolio-screenshots
make portfolio-verify
make test-offline
make lint
make typecheck
make evaluate-test
make report
```

Observed results:

- one real FastAPI/PostgreSQL/Playwright flow passed in 4.3 seconds and generated three sanitized
  1280-pixel-wide PNGs;
- 5/5 portfolio checks passed;
- 155 selected offline Python tests passed; 18 integration tests were intentionally deselected;
- 3 Vitest tests and the production frontend build passed;
- Ruff and strict mypy over 32 source files passed;
- the committed v4 freeze verified 28 files, 12 parts, 120 records, 9/9 targets, 20 reports,
  69/69 supported claims, and USD 0;
- no model, GPU, external provider, or paid call ran during Phase 11.

The screenshot verification used a separate temporary Compose project and environment; the user's
existing `.env` was not overwritten. Normal `make portfolio-screenshots` now starts only `app-db`.

## Repository state

- Project root: `/Users/mohammadrezakarami/Documents/New project/incidentgraph`
- Branch: `main`
- Remote: `https://github.com/mohammadrezakarami/incidentgraph.git`
- Remote visibility at creation: private
- The local branch already had two unpushed Phase 10 commits before Phase 11.
- No Phase 10 or Phase 11 changes were pushed because publication requires separate approval.

## Configuration and safety assumptions

- Python 3.12.14 and uv 0.12.17 are project-local; Node 24.13.1/npm 11.8.0 are pinned.
- The default model provider is disabled. Paid providers remain prohibited.
- The completed model runs used a free local-compatible path in Colab; heavy evaluation remains
  off the laptop.
- The runtime is loopback-only and read-only. It has no remediation, shell, Docker-socket, arbitrary
  PromQL/Cypher, production-data, or public-endpoint capability.
- The existing ignored root `.env` predates service-scoped identities and fails `make doctor` until
  each principal has a non-empty `service_ids` list. Do not overwrite it implicitly. A fresh valid
  file can be created with `.venv/bin/python scripts/create_local_env.py` after the user decides to
  replace or move the old file.
- Do not alter files hashed by the v1, v2, v3, or v4 freeze configurations.

## Remaining external work

There is no remaining roadmap phase. Optional next work is:

1. obtain explicit approval to push, then inspect GitHub CI/security, the full backend image build,
   and Trivy scan;
2. add independent domain review and a larger organization-independent dataset;
3. add enterprise identity, governed read-only telemetry credentials, sustained operational tests,
   and provider/privacy review before a real pilot;
4. create a separate deployment/security gate before any public endpoint;
5. keep automatic remediation out of scope unless a new authorization and rollback design is
   explicitly commissioned.

## Primary handoff documents

- `README.md`
- `docs/portfolio/FINAL_TECHNICAL_REPORT.md`
- `docs/portfolio/DEMO_SCRIPT.md`
- `docs/portfolio/DIAGRAMS.md`
- `docs/portfolio/CLAIMS_EVIDENCE.md`
- `docs/portfolio/TECHNICAL_DEFENSE.md`
- `docs/portfolio/FINAL_READINESS.md`
- `docs/progress/phase-11-report.md`
- `docs/progress/phase-10-report.md`
- `docs/progress/phase-09-report.md`
- `docs/progress/phase-09-repair.md`
- `docs/operations/RELEASE.md`
- `docs/security/THREAT_MODEL.md`

## Resume rule

Treat the local portfolio as complete. Do not rerun Phase 9 shards, make paid calls, push, publish,
deploy, expose endpoints, or replace the user's `.env` without a new explicit request.
