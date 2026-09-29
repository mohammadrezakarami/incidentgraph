# IncidentGraph Tasks

Last updated: 2026-09-29

Progress: **Phases 0–10 PASS; Phase 11 not started.** Historical Phase 9 v1/v3 FAIL results
remain preserved; the separately frozen v4 post-repair gate is the final passing result.

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

## Phase 8 — Observability and security hardening

- [x] Persist a server-generated W3C trace parent at investigation creation.
- [x] Correlate API, worker, model, and registered tool spans across durable execution.
- [x] Add bounded API/worker/model/tool Prometheus counters and latency histograms.
- [x] Exclude prompts, raw evidence, model output, tool arguments, and credentials from trace attributes.
- [x] Add recursive redaction before structured-log and trace serialization.
- [x] Add optional local JSONL trace rotation, backup count, and time retention.
- [x] Add non-mutating persisted-event retention preview and explicit apply operation.
- [x] Test prompt injection, unauthorized scope expansion, dependency outage, and secret sampling.
- [x] Record a lightweight local health-latency and IncidentGraph-container resource snapshot.
- [x] Preserve Phase 7 API and Phase 6 durability behavior with real PostgreSQL regressions.

Phase 8 gate result: **PASS**. The gate used deterministic model behavior, real local
FastAPI/PostgreSQL correlation, and a lightweight resource snapshot. It used no LLM, GPU, load
generator, external telemetry service, held-out evaluation, or paid call.

## Phase 9 — Frozen evaluation and error analysis

- [x] Verify both pre-existing held-out seals without exposing results.
- [x] Freeze prompts, workflow, scoring code, datasets, corpus, lockfile, model digest, and targets.
- [x] Freeze the zero-paid-cost run budget before held-out evaluation.
- [x] Implement equivalent fixed-workflow and adaptive-agent runners.
- [x] Implement one-pass vector/hybrid/graph held-out retrieval comparison.
- [x] Implement three repeats of a fixed 10-case development subset.
- [x] Implement one affordable held-out run for both workflows over all 30 incident cases.
- [x] Add per-case artifacts, resumable shards, aggregate reproduction, and failure sampling.
- [x] Add a free-Colab T4 notebook; keep the heavy run off the laptop.
- [x] Run all 12 Colab shards and return the final progress archive.
- [x] Complete the written rubric over 20 actual reports, labeled AI-assisted rather than independent human validation.
- [x] Publish target PASS/FAIL results and representative error analysis.

Phase 9 gate result: **FAIL — EVALUATION COMPLETE**. The free-Colab run completed 120/120 jobs at
USD 0 estimated cost and the aggregates reproduced byte-for-byte. Retrieval Recall@5,
appropriate abstention, and false-incident targets passed. Diagnosis Top 1/Top 3, citation validity,
policy violations, warm p95, supported-claim rate, and coverage failed. The claim-support review
measured 32/57 (56.1%) supported atomic claims against the frozen 95% target. That failure was
retained and followed by separately versioned v3/v4 iterations rather than rewriting v1.

### Phase 9 v3 — Fresh post-corpus iteration

- [x] Preserve the v1 and v2 results without changing their frozen files or claims.
- [x] Correct harmless structured-output normalization and unit-aware lab signal summaries.
- [x] Make incomplete telemetry physically absent from agent-readable captures.
- [x] Capture and verify 22 new post-corpus live scenarios with two runs per scenario.
- [x] Build a 60-case split with disjoint development and held-out capture groups.
- [x] Seal the fresh held-out digest before real-model evaluation.
- [x] Freeze the v3 model, code, data, captures, thresholds, and zero-paid-cost budget.
- [x] Prepare a resumable 12-shard free-Colab notebook and verified Git bundle.
- [x] Complete all 120 v3 model jobs in free Colab.
- [x] Reproduce aggregates and complete the written support rubric over at least 20 reports.
- [x] Publish the final Phase 9 v3 PASS/FAIL report without changing targets.

Phase 9 v3 gate result: **FAIL — EVALUATION COMPLETE**. All 120 jobs completed at estimated USD 0,
the aggregate and per-case outputs reproduced byte-for-byte, and 20 actual adaptive reports were
reviewed. Adaptive Top 1/Top 3 were 0/20, appropriate abstention was 3/5, false incidents were 0/5,
task completion was 30/30, and supported factual conclusions were 0/20. Coverage measured 48.38%
against the retained 85% target. Phase 9 is complete with an honest failed quality gate.

### Phase 9 quality repair — newly versioned iteration

- [x] Preserve and inspect the returned repair-2 raw probe without reinterpreting failures.
- [x] Scope every bounded signal and approved change to the exact service/dependency edge.
- [x] Move the synthetic-lab decision and report explanation out of unreliable free-form model text.
- [x] Add derived policy evidence linked to the complete source trace and raw evidence IDs.
- [x] Replay all 11 development capture groups, including reconstructed healthy-high-traffic:
  11/11 label and support checks, USD 0.
- [x] Add an end-to-end repaired workflow test.
- [x] Integrate repair-3 into a new workflow without changing any frozen v1/v2/v3 implementation.
- [x] Raise core-domain/policy/retrieval/orchestration coverage to the retained 85% target:
  85.14% branch-aware combined coverage, 145 tests passing.
- [x] Create and seal a genuinely fresh holdout before opening any new answers: 30 cases over 11
  new post-repair live capture groups, digest `b36dc01092ddc22565f061a4401b6710b9e77a46e5a10f3efc4a78058f23435d`.
- [x] Run the new frozen comparison for free off-laptop and complete the written claim-support rubric.

Repair-3 status: **PASS — PHASE 9 COMPLETE**. The v4 run completed all 120 jobs at USD 0 estimated
cost, reproduced byte-for-byte, and passed every frozen automated target. The written AI-assisted
review covered all 20 identifiable adaptive reports and found 69/69 supported atomic claims. It is
not independent human validation. The model selects observation order once per adaptive case but
cannot change trusted diagnosis or citation content.

## Phase 10 — Reproducible release and operations

- [x] Add deterministic CI and a separate service/browser job with frozen installs.
- [x] Add free secret, dependency/configuration, and container vulnerability workflows.
- [x] Keep real-model evaluation manually gated and out of normal CI.
- [x] Add the common non-root backend image and loopback-only release Compose overlay.
- [x] Add standard/low resource profiles and keep Ollama off by default.
- [x] Complete the documented Make command contract.
- [x] Add generated local configuration without committing secrets.
- [x] Implement checksum-backed PostgreSQL backup and explicitly confirmed restore.
- [x] Document Neo4j reconstruction, safe shutdown, reset, and troubleshooting.
- [x] Pass the offline deterministic suite after dependencies are present.
- [x] Pass a clean-clone core startup, migration, smoke, browser demo, and integration slice.
- [x] Verify backup/restore and safe shutdown against isolated clean-clone volumes.
- [x] Preserve the zero-paid-cost and no-heavy-local-model boundary.

Phase 10 gate result: **PASS**. The isolated clone passed 150 backend tests, 3 frontend tests, the
production build, 8 enabled integration tests, 1 Playwright end-to-end flow, frozen v4 evidence
replay, backup/restore, and teardown. Remote CI publication remains separately unauthorized.

## Later phase gates

The requested Phase 9 repair is complete. Historical failed versions and the final v4 evidence are
documented in `docs/progress/phase-09-repair.md`.

- [x] Phase 2: lab, telemetry, bounded faults, and independent captures.
- [x] Phase 3: graph, curated corpus, ingestion, embeddings, and indexes.
- [x] Phase 4: vector/hybrid/graph-enhanced retrieval and development comparison.
- [x] Phase 5: adaptive investigator and grounded reports, including the free real-model gate.
- [x] Phase 6: durability, review, recovery, cancellation, and follow-ups.
- [x] Phase 7: complete API and incident console.
- [x] Phase 8: observability and security hardening.
- [x] Phase 9: separately frozen v4 post-repair evaluation complete; quality gate **PASS**.
- [x] Phase 10: reproducible release and operations.
- [ ] Phase 11: portfolio handoff and technical defense.

## Explicitly deferred extensions

- Multiple agents.
- Automatic remediation.
- Kubernetes/Terraform/Kafka/service mesh.
- Separate vector database.
- Model training or fine-tuning.
- OpenRCA/AIOpsLab integration.
- Public deployment or production credentials.
