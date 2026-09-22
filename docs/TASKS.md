# IncidentGraph Tasks

Last updated: 2026-09-22

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

Phase 2 gate result: **PASS**. Await explicit approval before Phase 3.

## Later phase gates

- [x] Phase 2: lab, telemetry, bounded faults, and independent captures.
- [ ] Phase 3: graph, curated corpus, ingestion, embeddings, and indexes.
- [ ] Phase 4: vector/hybrid/graph-enhanced retrieval and development comparison.
- [ ] Phase 5: adaptive investigator and grounded reports; requires provider/budget approval.
- [ ] Phase 6: durability, review, recovery, cancellation, and follow-ups.
- [ ] Phase 7: complete API and incident console.
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
