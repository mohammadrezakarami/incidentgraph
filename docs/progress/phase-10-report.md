# Phase 10 report — reproducible release and operations

Date: 2026-09-29  
Status: **PASS**  
Acceptance revision: `ed44e6775d7d43833ac25b13cdd0da260476611f` plus the continuity-only
follow-up that records this report.

## Delivered release surface

- Added pinned, non-root `Dockerfile` configuration for the shared API/worker backend image.
- Added a loopback-only release Compose overlay and a separate low-resource override.
- Added long-running worker polling with SIGINT/SIGTERM graceful shutdown and lease-safe exit.
- Added a generated, ignored mode-0600 local `.env` path with independent secrets and a scoped
  operator token.
- Completed the Make interface for configure, capture, demo, offline tests, development/test
  evaluation, reports, release verification, image lifecycle, backup/restore, and explicit reset.
- Added non-overwriting PostgreSQL custom dumps, SHA-256 sidecars, checksum validation, archive
  validation, and an exact destructive restore confirmation.
- Added deterministic, service/browser, secret, dependency/configuration, container, and manual
  model-evaluation-guard GitHub workflows with frozen dependency installs.
- Added explicit license information and a release runbook covering clean clone, online/offline
  boundaries, resource profiles, backup/restore, safe shutdown, troubleshooting, and limitations.

## Clean-clone gate

A local clone was created from the acceptance revision at
`/private/tmp/incidentgraph-phase10-clean.0OBmxs/incidentgraph`. It did not reuse the source
checkout's virtual environment, `node_modules`, `.env`, or database volumes. A shared uv download
cache was supplied only to avoid downloading already available packages again; the clone created
its own uv binary, Python 3.12.14 runtime, virtual environment, and npm installation.

The clone used the isolated Compose project `incidentgraph-phase10-verify` and its own named
volumes. The original `incidentgraph` volumes were preserved. Verification results:

| Gate | Result |
|---|---:|
| Locked bootstrap | PASS — 111 Python packages and 115 npm packages installed |
| Generated configuration + `doctor` | PASS — no configuration problems |
| Release contract + Compose render | PASS — 8/8 checks, valid merged config |
| Offline deterministic backend | PASS — 150 passed, 18 integration tests deselected |
| Frontend unit tests | PASS — 3/3 |
| Production frontend build | PASS |
| Low-resource core startup | PASS — PostgreSQL, lab PostgreSQL, and Neo4j healthy |
| Migrations and connectivity smoke | PASS — 4 migrations; PostgreSQL/Neo4j true |
| Deterministic Playwright demo | PASS — 1/1 real API/browser flow |
| Default service integration slice | PASS — 8 passed, 7 separately gated tests skipped |
| Frozen v4 evidence replay | PASS — 12 parts, 120 jobs, 9/9 targets, USD 0 |
| PostgreSQL backup | PASS — 30,854-byte custom dump with matching SHA-256 sidecar |
| Destructive restore on isolated data | PASS — archive/list/restore and post-restore smoke |
| Safe shutdown | PASS — containers/network removed, named volumes retained |
| Dockerfile static build check | PASS — pinned bases, no warnings |

The first integration invocation from the restricted execution sandbox could not open local TCP
and failed with `Operation not permitted`. The identical command rerun with local-loopback access
passed 8/8 enabled tests; this was an execution-sandbox restriction, not a product failure.

## Offline and cost boundary

`make test-offline` used the installed `.venv` and `frontend/node_modules` directly with Hugging
Face and Transformers offline flags. It made no dependency, model, or provider request. The demo,
integration slice, evaluation replay, and backup/restore path made no model call. Paid monetary
cost for the Phase 10 gate was USD 0.

The optional Ollama profile stayed off. No Phase 9 shard was rerun, no hosted provider was
configured, and no GPU workload ran on the laptop.

## CI and release limitation

Workflow YAML parsed locally, action revisions are commit-pinned, and every deterministic command
behind the workflows passed locally. The private remote was not pushed and GitHub Actions were not
executed because the master specification requires separate publication approval. The full backend
image was therefore limited to Docker's static build check locally; its complete dependency-heavy
build and Trivy image scan remain assigned to remote CI so the laptop is not burdened. This is
visible release evidence, not a claim that unpublished remote checks already ran.

## Gate decision

Phase 10 is **PASS** for the local-first source release: a clean directory reproduced setup,
offline deterministic tests, real service startup, the documented browser demonstration,
evaluation replay, backup/restore, and safe teardown without a paid service. README commands and
the executable Make interface agree. Phase 11 is next.
