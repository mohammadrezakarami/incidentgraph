# IncidentGraph Tasks

Last updated: 2026-09-23

Progress: **Phase 6 is complete; 7/12 gates are complete including Phase 0.**

## Phase 0 — Discovery, architecture, and feasibility

- [x] Read the complete implementation specification.
- [x] Inspect workspace, instructions, Git state, host hardware, tools, and credential-variable presence.
- [x] Identify conflict with unrelated files in the parent workspace.
- [x] Define minimal core architecture and trust boundaries.
- [x] Define core-versus-extension boundary.
- [x] Propose provider/model and explicit cost gates.
- [x] Define local resource budget and heavy-run/Colab policy.
- [x] Define dataset and evaluation protocol.
- [x] Create five required ADRs.
- [x] Write Phase 0 report, project status, tasks, and handoff.
- [x] User approval to begin Phase 1.

## Phase 1 — Reproducible foundation and contracts

- [x] Initialize `/incidentgraph` as a standalone Git repository after approval.
- [x] Create and connect private `mohammadrezakarami/incidentgraph` GitHub repository.
- [x] Add focused `.gitignore` and secret/build-context exclusions.
- [x] Install and pin uv for the project; provision Python 3.12 without changing system Python.
- [x] Resolve exact Python dependencies and commit `uv.lock`.
- [x] Pin Node 24/npm and create frontend lockfile.
- [x] Pin all container images by exact version/digest after ARM64 probes.
- [x] Implement typed configuration and `doctor` command.
- [x] Implement initial evidence/report/request/error contracts.
- [x] Implement migrations for application tables and checkpoint namespace.
- [x] Implement minimal PostgreSQL job queue, lease, heartbeat, fencing, and event store.
- [x] Implement thin FastAPI skeleton and hashed development bearer-token authentication.
- [x] Run real PostgreSQL and Neo4j connectivity tests.
- [x] Demonstrate a non-AI job surviving a controlled worker restart.
- [x] Prove normal Compose teardown preserves persisted data.
- [x] Prove clean-clone bootstrap and checks.
- [x] Write Phase 1 report and update continuity documents.

Phase 1 gate result: **PASS**. Phase 2 was approved on 2026-09-22.

## Phase 2 — Lab telemetry and incident captures

- [x] User approval to begin Phase 2.
- [x] Implement three working transaction services and isolated lab storage.
- [x] Add bounded workload generation and safe operator-only fault controls.
- [x] Instrument metrics, structured logs, and propagated OpenTelemetry traces.
- [x] Implement six required fault families plus required controls.
- [x] Capture at least two independent live runs for each fault family.
- [x] Prove recovery and separate evaluator-only labels from runtime evidence.
- [x] Detect and correct the pool occupancy instrumentation error; rerun the full suite.
- [x] Write the Phase 2 report and update continuity documents.

Phase 2 gate result: **PASS**. Phase 3 was approved on 2026-09-23.

## Phase 3 — Knowledge graph and ingestion

- [x] User approval to begin Phase 3.
- [x] Define versioned Neo4j constraints, indexes, and declarative topology.
- [x] Validate dependency direction, reverse impact, endpoints, aliases, and temporal validity.
- [x] Create a curated 37-document corpus with hashes, licenses, versions, trust, and validity.
- [x] Implement structure-aware 500/75-token chunking with a 600-token hard cap.
- [x] Pin and locally cache the MiniLM model at an immutable Hub revision.
- [x] Validate 384-dimensional embedding compatibility and benchmark CPU behavior.
- [x] Implement incremental document/chunk upserts and archive removed sources.
- [x] Create and wait for Neo4j full-text and vector indexes.
- [x] Prove unchanged reruns skip embedding, interrupted partial state resumes safely, and updates replace stale chunks.
- [x] Write the Phase 3 report and update continuity documents.

Phase 3 gate result: **PASS**. Phase 4 was approved on 2026-09-23.

## Phase 4 — Retrieval baselines and development evaluation

- [x] User approval to begin Phase 4.
- [x] Define one typed contract for vector, hybrid, and graph-enhanced retrieval.
- [x] Enforce service authorization, trusted-source, environment, and as-of validity filters.
- [x] Implement 20-candidate vector and 20-candidate sanitized full-text retrieval.
- [x] Combine incomparable signals with reciprocal-rank fusion rather than raw-score addition.
- [x] Bound graph traversal to reviewed `DEPENDS_ON` edges, two hops, 50 nodes, and cycle-free paths.
- [x] Bound final context to eight deduplicated sources and 5,000 tokens.
- [x] Emit typed evidence with stable IDs, content hashes, validity, safe parameters, corpus snapshot, and exact graph-path provenance.
- [x] Create 40 grouped questions split into 20 development and 20 held-out cases.
- [x] Keep labels evaluator-only and seal the held-out questions/labels before development evaluation.
- [x] Implement Recall@5, MRR@5, and graded nDCG@5 with per-question artifacts.
- [x] Prove a downstream-only cache case is missed by direct baselines and recovered by graph retrieval.
- [x] Run all three variants on the same corpus version, cutoff, candidate limits, and context budget.
- [x] Write the Phase 4 report and update continuity documents.

Phase 4 gate result: **PASS**. Phase 5 was started with an explicit zero-cost constraint.

## Phase 5 — Adaptive investigator and grounded reports

- [x] Start Phase 5 without paid calls.
- [x] Create and seal 60 grouped incident evaluation cases before model tuning.
- [x] Implement the typed 12-node LangGraph workflow and strict model boundaries.
- [x] Implement all eight bounded read-only tool contracts.
- [x] Implement authorization, cutoff, novelty, call, token, cost, round, tool, and deadline policies.
- [x] Implement grounded report schemas, citation validation, contradictions, and inconclusive outcomes.
- [x] Configure the PostgreSQL checkpointer and immutable evidence/report persistence.
- [x] Keep raw telemetry outside checkpoint state.
- [x] Demonstrate different next-tool choices and abstention with deterministic model fixtures.
- [x] Test invalid model output, invalid citations, unauthorized/duplicate calls, and pre-call budget rejection.
- [x] Run an approved free real chat model against real read-only tools.
- [x] Demonstrate two real-model incidents that adapt to returned evidence.
- [x] Close the real-model gate and write the final Phase 5 result.

Phase 5 gate result: **PASS**. The two-case free Colab/Ollama/Qwen run passed all eight checks at zero monetary cost; both bounded reports safely abstained, persistence completed, and the held-out seal remained unchanged.

## Phase 6 — Durable execution, review, cancellation, and follow-ups

- [x] Start Phase 6 with PostgreSQL-only local verification and no model/GPU workload.
- [x] Bind queue leases and server-owned thread IDs to PostgreSQL LangGraph checkpoints.
- [x] Add generation-aware job recovery and fence stale completion/publication attempts.
- [x] Make report publication and lifecycle events idempotent.
- [x] Implement a real LangGraph human-review interrupt and controlled resume.
- [x] Release worker capacity while review is pending.
- [x] Bind review decisions to reviewer role/identity, investigation, report version, expiry, and idempotency key.
- [x] Reject unauthorized, stale, mismatched, repeated-effect, and expired review submissions safely.
- [x] Implement cooperative cancellation for queued, waiting, and running work.
- [x] Persist cumulative usage and implement explicitly budgeted, immutable report-version follow-ups.
- [x] Add review, cancellation, and follow-up API boundaries ahead of the full Phase 7 surface.
- [x] Pass kill/restart tests for expired leases, stale publication, checkpoint restart, review wait, and resume.

Phase 6 gate result: **PASS**. The gate used deterministic fixtures and the bounded local PostgreSQL container only; no real model, GPU, Ollama, paid call, or held-out evaluation ran.

## Phase 7 — API and incident console

- [x] Complete the versioned FastAPI contract, pagination, request IDs, request bounds, rate limiting, service authorization, and consistent errors.
- [x] Add authenticated SSE with persisted sequence IDs, `Last-Event-ID`, heartbeat, bounded connection lifetime, and reconnect behavior.
- [x] Add owner/operator checks for records, streams, reports, evidence, follow-ups, cancellation, and HTTP review access.
- [x] Connect the production worker entrypoint to the fenced durable coordinator without a fake-model fallback.
- [x] Persist bounded tool/model decision events for the live console timeline.
- [x] Build the React/TypeScript/Vite console with API-backed history, create form, LIVE/REPLAY states, timeline, report, evidence, metric chart, and dependency graph.
- [x] Add human-review meaning, cancellation, follow-up, loading, partial, reconnect, empty, and accessible error states.
- [x] Create the local threat model before broadening the API surface.
- [x] Pass Vitest, production build, real API/PostgreSQL contract, cross-user, SSE resume, and Playwright end-to-end gates.

Phase 7 gate result: **PASS**. The gate used no model, GPU, Ollama, paid call, or held-out evaluation. Its browser worker is an explicitly labeled deterministic test fixture that publishes through the real PostgreSQL lease/publication contract.

## Later phase gates

- [x] Phase 2: lab, telemetry, bounded faults, and independent captures.
- [x] Phase 3: graph, curated corpus, ingestion, embeddings, and indexes.
- [x] Phase 4: vector/hybrid/graph-enhanced retrieval and development comparison.
- [x] Phase 5: adaptive investigator and grounded reports, including the free real-model gate.
- [x] Phase 6: durability, review, recovery, cancellation, and follow-ups.
- [x] Phase 7: complete API and incident console.
- [ ] Phase 8: observability and security hardening.
- [ ] Phase 9: frozen evaluation; requires a separate approved run budget.
- [ ] Phase 10: reproducible release and operations.
- [ ] Phase 11: portfolio handoff and technical defense.

## Explicitly deferred extensions

- Multiple agents.
- Automatic remediation.
- Kubernetes/Terraform/Kafka/service mesh.
- Separate vector database.
- Model training or fine-tuning.
- OpenRCA/AIOpsLab integration.
- Public deployment or production credentials.
