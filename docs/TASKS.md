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
- [ ] Install and pin uv for the project; provision Python 3.12 without changing system Python.
- [ ] Resolve exact Python dependencies and commit `uv.lock`.
- [ ] Pin Node 24/npm and create frontend lockfile.
- [ ] Pin all container images by exact version/digest after ARM64 probes.
- [ ] Implement typed configuration and `doctor` command.
- [ ] Implement initial evidence/report/request/error contracts.
- [ ] Implement migrations for application tables and checkpoint namespace.
- [ ] Implement minimal PostgreSQL job queue, lease, heartbeat, fencing, and event store.
- [ ] Implement thin FastAPI skeleton and hashed development bearer-token authentication.
- [ ] Run real PostgreSQL and Neo4j connectivity tests.
- [ ] Demonstrate a non-AI job surviving a controlled worker restart.
- [ ] Write Phase 1 report and update continuity documents.

## Later phase gates

- [ ] Phase 2: lab, telemetry, bounded faults, and independent captures.
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
