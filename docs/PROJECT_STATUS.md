# IncidentGraph Project Status

Last updated: 2026-09-29

## Current phase

Phase 1 — Reproducible foundation and contracts: **PASS**.

Phase 2 — Lab telemetry and incident captures: **PASS**.

Phase 3 — Knowledge graph and ingestion: **PASS**.

Phase 4 — Retrieval baselines and development evaluation: **PASS**.

Phase 5 — Adaptive investigator and grounded reports: **PASS**.

Phase 6 — Durable execution, review, cancellation, and follow-ups: **PASS**.

Phase 7 — API and incident console: **PASS**.

Phase 8 — Observability and security hardening: **PASS**.

Phase 9 — Frozen evaluation and error analysis: **PASS (separately frozen v4 repair)**.

Phase 10 — Reproducible release and operations: **PASS**.

Roadmap position: **Phases 0–10 passed; Phase 11 has not started.** The immutable Phase 9 v1 and v3
evaluations remain FAIL; the later separately frozen v4 post-repair gate is PASS.

See `docs/progress/phase-09-repair.md` for the returned repair-2 failure, repair-3's trusted bounded
policy, and the final v4 result. Repair-3 is integrated into the separately versioned v4 workflow,
145 non-integration tests pass, and branch-aware core coverage is 85.14%. The sealed 30-case
holdout came from 11 new post-repair live captures. Its zero-cost Colab execution completed 120/120
jobs, and the written review found 69/69 supported claims across 20 actual reports.

The foundation, telemetry lab, operational graph, corpus ingestion, retrieval layer, adaptive
investigator, durable human-review lifecycle, API/console, and observability/security hardening are
implemented and verified. Phase 9 preserved its failed historical evaluations, then completed a
newly sealed zero-cost v4 evaluation and passed every unchanged target in that versioned gate.
Phase 10 added release/CI configuration, resource profiles, backup/restore, safe shutdown, and a
clean-clone proof covering offline tests plus the real deterministic browser demonstration.

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
- Ruff, strict mypy over 31 source files, 145 selected Python non-integration tests, 3 Vitest tests,
  the production frontend build, the real Phase 8 trace/security integration, the Phase 7 API
  contract, 6 Phase 6 queue/recovery tests, and prior Playwright/checkpoint gates pass; earlier live
  lab, graph-ingestion, retrieval, and Phase 5 gates also passed.
- Safe Compose teardown preserves named-volume data.
- Three real transaction services, Redis, and Prometheus are healthy.
- Twelve independent live fault captures and five control captures pass executable verification.
- Evaluator labels are separate from agent-readable captures and absent from the runtime image.
- The declarative graph contains 3 services, 3 resources, 2 directed dependencies, versioned provenance, deployments, and reviewed synthetic incidents.
- The curated corpus contains 37 documents and 37 chunks; 34 documents are eligible at the current cutoff.
- Full-text and 384-dimensional cosine vector indexes are `ONLINE` and incremental reruns skip unchanged content.
- The pinned MiniLM CPU benchmark encoded 37 chunks in 0.14048 seconds (263.383 chunks/second) on the inspected Mac.
- Vector, reciprocal-rank hybrid, and graph-enhanced hybrid retrieval share one bounded contract: 20 candidates per signal, graph depth at most 2, graph node cap 50, final context at most 8 chunks and 5,000 tokens.
- The sealed 20-question development comparison scored graph retrieval at Recall@5 0.908, MRR@5 1.000, and nDCG@5 0.957. The later frozen Phase 9 held-out comparison scored graph Recall@5 0.925.
- The required downstream-only case is executable: direct vector and direct hybrid miss the payment-cache evidence, while graph retrieval introduces it over `gateway -> checkout -> payments` with exact relationship provenance.
- No relevant provider/API-key environment variable names were detected.
- The Phase 5 workflow has all 12 required nodes, strict structured boundaries, eight read-only tools, deterministic budgets, grounded report validation, and PostgreSQL checkpoints.
- Full evidence and final reports are stored immutably in PostgreSQL; checkpoint state retains bounded summaries and evidence references rather than raw telemetry.
- The incident evaluation manifest contains 60 cases split 30/30 with the required class balance. The held-out seal is `1dbac7ea0da7702ad13c387743c2c5c795e45f3d81c78d857a98095cf25d8b67`; the frozen held-out run is now complete.
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
- The Phase 9 free-Colab run completed 120/120 agent jobs and 20 held-out retrieval questions at USD 0 estimated cost. Re-finalization reproduced the returned aggregate and per-case hashes exactly.
- Held-out graph retrieval reached Recall@5 0.925. Adaptive reports reached 5/5 appropriate abstentions and 0/5 false incidents, but diagnosis Top 1 and Top 3 were both 0/20, citation validity was 77/78, task completion was 28/30, and warm p95 was 280.463 seconds.
- The written claim-support rubric reviewed 20 actual reports and found 32/57 (56.1%) supported atomic claims. It is labeled AI-assisted and is not claimed as independent human validation.
- The returned repair-2 development probe produced 10 valid reports but only 7/10 eventual label
  matches (6/10 first-pass) and several false rationales; its raw responses are preserved rather
  than rescored. Repair-3 moves the synthetic-lab decision, exact citations and explanation text
  into trusted service-scoped policy code. Its consumed eleven-case replay (including the
  reconstructed healthy-high-traffic control) is 11/11 with 11/11 deterministic support checks,
  zero model calls and USD 0; it is not a fresh held-out result.
- The separately versioned v3 surface contains 22 fresh post-corpus live captures: two independent
  runs for every six fault families and every five control scenarios. Hashes, fault effects,
  recovery, trace continuity, evaluator separation, and telemetry contracts all pass.
- The v3 incident fixture contains 60 newly sealed cases with the required 30/30 split and class
  balance. Development and held-out use disjoint sets of 11 capture groups; its held-out digest is
  `bca9a7735948a5946271ec6329c4fefda476959757feb673d5739a1b3293a8cc`.
- The v3 development-only preflight matched the expected bounded signal/healthy/ambiguity contract
  for all 11 development capture groups.
- The v3 free-Colab run completed 120/120 jobs at estimated USD 0. Its pre-review aggregate SHA-256
  is `e9a2cb42e31f3aadbf0111796093084ddc9c3287cddbb08ea5a99541385808ce`, and local finalization
  reproduced both aggregate and per-case artifacts byte-for-byte.
- Fresh v3 adaptive results were Top 1 0/20, Top 3 0/20, appropriate abstention 3/5, false incidents
  0/5, task completion 30/30, zero policy violations, and 17.269 seconds warm p95 active duration.
- The v3 written rubric reviewed 20 actual reports and found 0/20 supported factual conclusions;
  every sampled report left the structured claim fields empty and emitted one uncited generic
  conclusion. The review is AI-assisted and not independent human validation.
- The v4 free-Colab run completed 120/120 jobs at estimated USD 0. Re-finalization reproduced the
  returned pre-review aggregate and per-case CSV byte-for-byte. Archive SHA-256 is
  `47f77a40175203d3f2ee4d44e2b7baf5d26e4d9de1a7046ab238e5913fd98bcc`.
- Fresh v4 fixed and adaptive results were Top 1 20/20, Top 3 20/20, appropriate abstention 5/5,
  zero false incidents, 30/30 task completion, 100% citation validity, and zero policy violations.
  Adaptive warm p95 active duration was 1.819 seconds.
- The v4 written rubric reviewed all 20 identifiable adaptive reports across seven represented
  capture groups and found 69/69 supported atomic claims. The review is AI-assisted and is not
  independent human validation.
- The Phase 10 clean clone installed its own locked runtimes/dependencies, passed 150 offline
  backend tests, 3 frontend tests, the production frontend build, 8 enabled service integration
  tests, and the real deterministic Playwright flow. Its isolated backup/restore and post-restore
  smoke also passed; all Phase 10 model and paid-service usage remained zero.

## Approved decisions recorded in ADRs

- Accepted: one adaptive investigator.
- Accepted: Neo4j Community for graph plus document vector/full-text retrieval.
- Accepted: PostgreSQL-backed queue/events/reviews/checkpoints with explicit leases and fencing.
- Accepted: immutable replay snapshots isolated by cutoff.
- Accepted: read-only investigation with no remediation execution.

## Open gates and limitations

- Phase 9 v1 and the separately frozen fresh v3 iteration are both complete with historical
  **FAIL** results. Their measured failures are retained without post-held-out tuning or target
  changes; the independently versioned v4 repair is the final **PASS** gate.
- The historical v3 whole-package command measured 48.38%. The specification's explicit v4 core
  domain/policy/retrieval/orchestration scope now measures 85.14% with branch coverage enabled.
- V4 final aggregate and supported-claim results are complete; all sealed inputs and frozen targets
  remained unchanged after the result was opened.
- Phase 2 captures still predate most Phase 3 corpus validity windows in the immutable v1 result;
  v3 uses newly captured and separately sealed post-corpus cases instead of rewriting history.
- Development metrics are based on a small project-authored laboratory corpus and must not be presented as held-out or production quality.
- Hybrid is slightly below vector on this development set; no tuning against held-out data is allowed.
- Paid provider access remains intentionally unapproved; the completed Phase 5 evidence uses only the free local-compatible Colab path.
- The existing untracked local `.env` needs an explicit `service_ids` list on each principal before interactive use; an omitted scope fails closed rather than authorizing all services.
- Phase 10 GitHub workflow files are present and syntactically validated, but remain unpushed and
  unexecuted remotely because publication requires separate approval. The dependency-heavy backend
  image received Docker's static build check locally; its full build and Trivy image scan are left
  to remote CI to avoid burdening the laptop.

## Repository

- Local: `/Users/mohammadrezakarami/Documents/New project/incidentgraph`
- Remote: `https://github.com/mohammadrezakarami/incidentgraph`
- Visibility: private at creation time

## Evidence

See `docs/progress/phase-10-report.md` for the release gate and clean-clone evidence. Complete v1,
fresh v3, and final
v4 returned runs, reproduced aggregates, and written rubrics are under
`artifacts/evaluation/phase9-frozen-v1/`, `artifacts/evaluation/phase9-v3-fresh/`, and
`artifacts/evaluation/phase9-v4-fresh/`.
