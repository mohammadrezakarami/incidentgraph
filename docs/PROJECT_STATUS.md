# IncidentGraph Project Status

Last updated: 2026-09-23

## Current phase

Phase 1 — Reproducible foundation and contracts: **PASS**.

Phase 2 — Lab telemetry and incident captures: **PASS**.

Phase 3 — Knowledge graph and ingestion: **PASS**.

Phase 4 — Retrieval baselines and development evaluation: **AWAITING USER APPROVAL**.

Roadmap position: **Phase 3 of 11 delivery phases is complete. Including discovery Phase 0, 4 of 12 gated phases are complete and 8 remain.**

The foundation, telemetry lab, operational graph, and corpus ingestion are implemented and verified. It is not an AI investigator yet.

## Verified environment

- Apple Silicon MacBook Air, Apple M4, 10 CPU cores, 16 GiB RAM.
- Approximately 95 GiB free storage at inspection time.
- macOS 26.6.2, ARM64.
- Host Python remains unchanged; project-local Python 3.12.14 is installed under `.tools`.
- Project-local uv 0.12.17 is installed and `uv.lock` resolves 133 package records across supported platforms.
- Node v24.13.1 and npm 11.8.0 are installed; Node 24 is an active LTS line.
- Docker 29.4.1 and Docker Compose v5.1.3 clients are installed.
- Docker daemon is running on Linux/ARM64 with 10 CPUs and approximately 8 GiB assigned.
- Digest-pinned PostgreSQL 18.6 and Neo4j 2026.09.0 services are healthy; real connectivity passes.
- Ruff, strict mypy over 15 source files, 22 unit tests, 1 real PostgreSQL recovery test, 2 live lab tests, and 1 real graph-ingestion test pass.
- Safe Compose teardown preserves named-volume data.
- Three real transaction services, Redis, and Prometheus are healthy.
- Twelve independent live fault captures and five control captures pass executable verification.
- Evaluator labels are separate from agent-readable captures and absent from the runtime image.
- The declarative graph contains 3 services, 3 resources, 2 directed dependencies, versioned provenance, deployments, and reviewed synthetic incidents.
- The curated corpus contains 37 documents and 37 chunks; 34 documents are eligible at the current cutoff.
- Full-text and 384-dimensional cosine vector indexes are `ONLINE` and incremental reruns skip unchanged content.
- The pinned MiniLM CPU benchmark encoded 37 chunks in 0.14048 seconds (263.383 chunks/second) on the inspected Mac.
- No relevant provider/API-key environment variable names were detected.

## Approved decisions recorded in ADRs

- Accepted: one adaptive investigator.
- Accepted: Neo4j Community for graph plus document vector/full-text retrieval.
- Accepted: PostgreSQL-backed queue/events/reviews/checkpoints with explicit leases and fencing.
- Accepted: immutable replay snapshots isolated by cutoff.
- Accepted: read-only investigation with no remediation execution.

## Open gates and limitations

- Phase 4 requires user approval.
- The current API enqueues only an explicitly non-AI durability job.
- The retained 85 percent coverage command currently reports 38.71 percent over all modules; the later core target is not yet met.
- Phase 2 captures predate the Phase 3 corpus and must not be used as final as-of benchmark cases without recapture.
- Retrieval variants and retrieval-quality measurements begin in Phase 4; index readiness alone is not a retrieval-quality claim.
- Provider access and paid-call budget are intentionally unapproved and are not needed before Phase 5.

## Repository

- Local: `/Users/mohammadrezakarami/Documents/New project/incidentgraph`
- Remote: `https://github.com/mohammadrezakarami/incidentgraph`
- Visibility: private at creation time

## Evidence

See `docs/progress/phase-03-report.md` for commands, measurements, limitations, and gate evidence.
