# IncidentGraph Project Status

Last updated: 2026-09-23

## Current phase

Phase 1 — Reproducible foundation and contracts: **PASS**.

Phase 2 — Lab telemetry and incident captures: **PASS**.

Phase 3 — Knowledge graph and ingestion: **PASS**.

Phase 4 — Retrieval baselines and development evaluation: **PASS**.

Phase 5 — Adaptive investigator and grounded reports: **IN PROGRESS; REAL-MODEL GATE BLOCKED**.

Roadmap position: **Phase 5 of 11 delivery phases is active. Including discovery Phase 0, 5 of 12 gated phases are complete, 1 is active, and 6 later phases have not started.**

The foundation, telemetry lab, operational graph, corpus ingestion, retrieval layer, and deterministic investigator foundation are implemented and verified. A real chat model has not yet driven the tools, so the Phase 5 gate is not passed.

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
- Ruff, strict mypy over 19 source files, 41 unit tests, and 2 Phase 5 integration tests pass; earlier PostgreSQL recovery, live lab, graph-ingestion, and retrieval integration tests also passed at their phase gates.
- Safe Compose teardown preserves named-volume data.
- Three real transaction services, Redis, and Prometheus are healthy.
- Twelve independent live fault captures and five control captures pass executable verification.
- Evaluator labels are separate from agent-readable captures and absent from the runtime image.
- The declarative graph contains 3 services, 3 resources, 2 directed dependencies, versioned provenance, deployments, and reviewed synthetic incidents.
- The curated corpus contains 37 documents and 37 chunks; 34 documents are eligible at the current cutoff.
- Full-text and 384-dimensional cosine vector indexes are `ONLINE` and incremental reruns skip unchanged content.
- The pinned MiniLM CPU benchmark encoded 37 chunks in 0.14048 seconds (263.383 chunks/second) on the inspected Mac.
- Vector, reciprocal-rank hybrid, and graph-enhanced hybrid retrieval share one bounded contract: 20 candidates per signal, graph depth at most 2, graph node cap 50, final context at most 8 chunks and 5,000 tokens.
- The sealed 20-question development comparison scored graph retrieval at Recall@5 0.908, MRR@5 1.000, and nDCG@5 0.957; the 20-question held-out split was not evaluated.
- The required downstream-only case is executable: direct vector and direct hybrid miss the payment-cache evidence, while graph retrieval introduces it over `gateway -> checkout -> payments` with exact relationship provenance.
- No relevant provider/API-key environment variable names were detected.
- The Phase 5 workflow has all 12 required nodes, strict structured boundaries, eight read-only tools, deterministic budgets, grounded report validation, and PostgreSQL checkpoints.
- Full evidence and final reports are stored immutably in PostgreSQL; checkpoint state retains bounded summaries and evidence references rather than raw telemetry.
- The incident evaluation manifest contains 60 cases split 30/30 with the required class balance. The held-out seal is `1dbac7ea0da7702ad13c387743c2c5c795e45f3d81c78d857a98095cf25d8b67` and has not been evaluated.

## Approved decisions recorded in ADRs

- Accepted: one adaptive investigator.
- Accepted: Neo4j Community for graph plus document vector/full-text retrieval.
- Accepted: PostgreSQL-backed queue/events/reviews/checkpoints with explicit leases and fencing.
- Accepted: immutable replay snapshots isolated by cutoff.
- Accepted: read-only investigation with no remediation execution.

## Open gates and limitations

- Phase 5's real-model gate is blocked: paid calls are prohibited, `MODEL_PROVIDER` is disabled, and no suitable free local chat runtime/model is installed.
- The current API enqueues only an explicitly non-AI durability job.
- The retained 85 percent coverage command currently reports 48.17 percent over all modules; the later core target is not yet met.
- Phase 2 captures predate the Phase 3 corpus and must not be used as final as-of benchmark cases without recapture.
- Development metrics are based on a small project-authored laboratory corpus and must not be presented as held-out or production quality.
- Hybrid is slightly below vector on this development set; no tuning against held-out data is allowed.
- Provider access and paid-call budget remain intentionally unapproved.

## Repository

- Local: `/Users/mohammadrezakarami/Documents/New project/incidentgraph`
- Remote: `https://github.com/mohammadrezakarami/incidentgraph`
- Visibility: private at creation time

## Evidence

See `docs/progress/phase-05-report.md` for the active phase and `docs/progress/phase-04-report.md` plus `artifacts/evaluation/phase4-dev/` for the latest completed gate.
