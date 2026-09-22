# IncidentGraph Project Status

Last updated: 2026-09-22

## Current phase

Phase 1 — Reproducible foundation and contracts: **PASS**.

Phase 2 — Lab telemetry and incident captures: **AWAITING USER APPROVAL**.

The foundation is implemented and verified. It is not an AI investigator yet.

## Verified environment

- Apple Silicon MacBook Air, Apple M4, 10 CPU cores, 16 GiB RAM.
- Approximately 95 GiB free storage at inspection time.
- macOS 26.6.2, ARM64.
- Host Python remains unchanged; project-local Python 3.12.14 is installed under `.tools`.
- Project-local uv 0.12.17 is installed and `uv.lock` resolves 85 installed packages.
- Node v24.13.1 and npm 11.8.0 are installed; Node 24 is an active LTS line.
- Docker 29.4.1 and Docker Compose v5.1.3 clients are installed.
- Docker daemon is running on Linux/ARM64 with 10 CPUs and approximately 8 GiB assigned.
- Digest-pinned PostgreSQL 18.6 and Neo4j 2026.09.0 services are healthy; real connectivity passes.
- Clean-clone bootstrap, Ruff, strict mypy, 9 unit tests, and 1 real PostgreSQL recovery test pass.
- Safe Compose teardown preserves named-volume data.
- No relevant provider/API-key environment variable names were detected.

## Approved decisions recorded in ADRs

- Accepted: one adaptive investigator.
- Accepted: Neo4j Community for graph plus document vector/full-text retrieval.
- Accepted: PostgreSQL-backed queue/events/reviews/checkpoints with explicit leases and fencing.
- Accepted: immutable replay snapshots isolated by cutoff.
- Accepted: read-only investigation with no remediation execution.

## Open gates and limitations

- Phase 2 requires user approval.
- The current API enqueues only an explicitly non-AI durability job.
- The retained 85 percent coverage command currently reports 51.09 percent over all foundation modules; the later core target is not yet met.
- Provider access and paid-call budget are intentionally unapproved and are not needed before Phase 5.

## Repository

- Local: `/Users/mohammadrezakarami/Documents/New project/incidentgraph`
- Remote: `https://github.com/mohammadrezakarami/incidentgraph`
- Visibility: private at creation time

## Evidence

See `docs/progress/phase-01-report.md` for commands, measurements, limitations, and gate evidence.
