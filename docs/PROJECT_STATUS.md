# IncidentGraph Project Status

Last updated: 2026-09-24

## Current phase

Phase 1 — Reproducible foundation and contracts: **PASS**.

Phase 2 — Lab telemetry and incident captures: **PASS**.

Phase 3 — Knowledge graph and ingestion: **PASS**.

Phase 4 — Retrieval baselines and development evaluation: **PASS**.

Phase 5 — Adaptive investigator and grounded reports: **PASS**.

Phase 6 — Durable execution, review, cancellation, and follow-ups: **PASS**.

Phase 7 — API and incident console: **PASS**.

Phase 8 — Observability and security hardening: **PASS**.

Phase 9 — Frozen evaluation and error analysis: **IN PROGRESS — FROZEN, COLAB RUN PENDING**.

Roadmap position: **Phase 8 of 11 delivery phases is complete. Including discovery Phase 0, 9 of 12 gated phases are complete; Phase 9 is frozen but not yet passed, and Phases 10–11 have not started.**

The foundation, telemetry lab, operational graph, corpus ingestion, retrieval layer, adaptive investigator, durable human-review lifecycle, API/console, and observability/security hardening are implemented and verified. Phase 8 required no model, GPU, held-out evaluation, external telemetry service, or paid call; it used deterministic security fixtures and real local API/PostgreSQL trace correlation.

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
- Ruff, strict mypy over 23 source files, 62 Python unit tests, 3 Vitest tests, the production frontend build, the real Phase 8 trace/security integration, the Phase 7 API contract, 6 Phase 6 queue/recovery tests, and prior Playwright/checkpoint gates pass; earlier live lab, graph-ingestion, retrieval, and Phase 5 gates also passed.
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
- The Phase 5 free real-model artifact passed all eight checks for two development cases with Ollama 0.34.3 and `qwen3:4b-instruct-2507-q4_K_M` at digest `0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`.
- Both real-model cases safely returned citation-valid `inconclusive` reports after bounded model-output failures; no cause was invented, PostgreSQL checkpoints completed, and estimated cost remained USD 0.
- Queue attempts are fenced by owner, token, expiration, generation, and target report version. Publication is atomic and idempotent, and stale attempts cannot publish.
- Human-review waits clear the worker lease. Decisions are role-checked, version-bound, expiring, idempotent, and stored before a controlled resume attempt is queued.
- Cooperative cancellation prevents a requested run from completing or publishing after the worker observes the request; already-issued provider work cannot be retroactively reversed.
- Follow-ups retain cumulative usage, require an explicit incremental model/tool budget, continue the same checkpoint thread, and publish a new immutable report version.
- The API now exposes the complete versioned contract with owner/operator enforcement, request IDs, payload and pagination bounds, per-principal local rate limiting, canonical service authorization, consistent errors, report/evidence access, time-aware dependencies, operator-only metrics, and resumable authenticated SSE.
- The React console displays only API-backed facts and supports LIVE/REPLAY labeling, all lifecycle states, event reconnect, evidence drill-down, metric charts, a lazy-loaded Cytoscape dependency view, review/cancellation/follow-up controls, partial/error states, keyboard focus, responsive layout, and safe text rendering.
- The Playwright gate creates a real queued investigation through the browser, reconnects from `Last-Event-ID`, publishes through the fenced PostgreSQL worker contract with a clearly labeled deterministic fixture, opens the cited record, accepts review without executing remediation, preserves state across refresh, and proves cross-user access returns 404.
- Optional local tracing now correlates API, durable worker, model, and registered tool spans through a PostgreSQL-stored W3C parent. Prompts, questions, raw evidence, model output, DSNs, and authorization data are excluded from trace attributes; recursive redaction is applied before export.
- Operational Prometheus counters/histograms cover API, worker, model, and tool activity with bounded labels. Local JSONL traces rotate by size and retention, while persisted event retention has a non-mutating preview and explicit apply operation.
- Phase 8 adversarial tests reject injected shell-like fields and unauthorized service expansion, verify fail-closed source outages without raw exception text, and sample correlated traces for the test bearer secret.
- The lightweight recorded profile completed 25/25 loopback health requests with 0.397 ms median and 0.584 ms p95; the eight IncidentGraph containers used about 1.27 GiB in that snapshot. The artifact is a point-in-time local observation, not an investigation benchmark or production SLO.

## Approved decisions recorded in ADRs

- Accepted: one adaptive investigator.
- Accepted: Neo4j Community for graph plus document vector/full-text retrieval.
- Accepted: PostgreSQL-backed queue/events/reviews/checkpoints with explicit leases and fencing.
- Accepted: immutable replay snapshots isolated by cutoff.
- Accepted: read-only investigation with no remediation execution.

## Open gates and limitations

- Phase 9 seals, prompts, model digest, scoring code, corpus, and zero-cost budget are frozen and verify. The 12 resumable free-Colab shards, held-out aggregates, and 20-report manual rubric remain pending.
- The retained 85 percent coverage command currently reports 49.45 percent over all modules; the later core target is not yet met.
- Phase 2 captures predate most Phase 3 corpus validity windows. The frozen Phase 9 run records this limitation and will not rewrite timestamps or seals; a later dataset version requires newly captured and newly sealed cases.
- Development metrics are based on a small project-authored laboratory corpus and must not be presented as held-out or production quality.
- Hybrid is slightly below vector on this development set; no tuning against held-out data is allowed.
- Paid provider access remains intentionally unapproved; the completed Phase 5 evidence uses only the free local-compatible Colab path.
- The existing untracked local `.env` needs an explicit `service_ids` list on each principal before interactive use; an omitted scope fails closed rather than authorizing all services.

## Repository

- Local: `/Users/mohammadrezakarami/Documents/New project/incidentgraph`
- Remote: `https://github.com/mohammadrezakarami/incidentgraph`
- Visibility: private at creation time

## Evidence

See `docs/progress/phase-09-report.md` for current frozen-evaluation progress and `docs/progress/phase-08-report.md` for the latest completed gate. The Phase 9 heavy run has no result artifact yet.
