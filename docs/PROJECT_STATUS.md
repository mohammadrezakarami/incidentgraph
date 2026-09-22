# IncidentGraph Project Status

Last updated: 2026-09-22

## Current phase

Phase 1 — Reproducible foundation and contracts: **IN PROGRESS**.

Phase 0 passed. Phase 1 was approved on 2026-09-22. The standalone local repository and private GitHub repository now exist; implementation contracts and service foundations have not yet been added.

## Verified environment

- Apple Silicon MacBook Air, Apple M4, 10 CPU cores, 16 GiB RAM.
- Approximately 95 GiB free storage at inspection time.
- macOS 26.6.2, ARM64.
- Host Python 3.14.2; required Python 3.12 is not installed as the selected project runtime.
- `uv` is not installed.
- Node v24.13.1 and npm 11.8.0 are installed; Node 24 is an active LTS line.
- Docker 29.4.1 and Docker Compose v5.1.3 clients are installed.
- Docker daemon is running on Linux/ARM64 with 10 CPUs and approximately 8 GiB assigned; no project container compatibility test has passed yet.
- No relevant provider/API-key environment variable names were detected.

## Approved decisions recorded in ADRs

- Proposed, awaiting Phase 1 approval: one adaptive investigator.
- Proposed: Neo4j Community for graph plus document vector/full-text retrieval.
- Proposed: PostgreSQL-backed queue/events/reviews/checkpoints with explicit leases and fencing.
- Proposed: immutable replay snapshots isolated by cutoff.
- Proposed: read-only investigation with no remediation execution.

## Current blockers

- Exact dependency and container compatibility probes have not run yet.
- Provider access and paid-call budget are intentionally unapproved and are not needed before Phase 5.

## Repository

- Local: `/Users/mohammadrezakarami/Documents/New project/incidentgraph`
- Remote: `https://github.com/mohammadrezakarami/incidentgraph`
- Visibility: private at creation time

## Evidence

See `docs/progress/phase-00-report.md` for commands, sources, assumptions, risks, estimates, and acceptance results.
