# CV claims and evidence map

Use these only under a **Personal Projects** heading. IncidentGraph is not paid work, a public
production deployment, or evidence of business impact. Each statement below is deliberately scoped
to the implemented laboratory system.

## Paste-ready CV bullets

### CV-1 — Stateful investigator

**Statement.** Built a 12-node, stateful infrastructure-incident investigator with LangGraph and
LangChain structured model/tool contracts, eight read-only tools, deterministic policy and budget
checks, PostgreSQL checkpoint recovery, and durable human review.

**Implementation evidence.** `src/incidentgraph/investigator.py`,
`src/incidentgraph/investigation_tools.py`, `src/incidentgraph/durability.py`,
`src/incidentgraph/persistence.py`, and `ops/migrations/003_durability.sql`.

**Verification evidence.**
`tests/unit/test_investigator.py::test_workflow_contains_every_required_phase5_lifecycle_node`,
`tests/unit/test_investigator.py::test_policy_rejects_unauthorized_and_duplicate_tool_calls`,
`tests/integration/test_phase5_investigator.py::test_review_interrupt_resumes_after_workflow_process_restart`,
and `tests/integration/test_durable_queue.py::test_review_wait_releases_lease_and_recovery_fences_stale_publication`.

**Scope.** One sequential investigator, one active run per worker, local laboratory evidence, and
read-only recommendations. At-least-once delivery is made safe through fencing and idempotent
effects; this is not an exactly-once claim.

### CV-2 — Versioned GraphRAG retrieval

**Statement.** Implemented versioned Neo4j GraphRAG over a 37-document project-authored corpus,
combining vector, full-text, and authorization-filtered dependency expansion; graph retrieval
reached 0.925 Recall@5 on a sealed 20-question laboratory holdout.

**Implementation evidence.** `src/incidentgraph/ingestion.py`,
`src/incidentgraph/retrieval.py`, `config/graph_schema.cypher`, `config/topology.json`,
`data/corpus/manifest.jsonl`, and `data/corpus/documents.json`.

**Verification evidence.**
`tests/integration/test_phase3_graph.py::test_incremental_ingestion_is_idempotent_and_replaces_changed_chunks`,
`tests/integration/test_phase4_retrieval.py::test_three_retrievers_share_contract_and_graph_recovers_downstream_evidence`,
`artifacts/evaluation/phase9-frozen-v1/retrieval-heldout.json`, and
`artifacts/evaluation/phase9-frozen-v1/summary.md`.

**Dataset and result scope.** Twenty sealed, project-authored laboratory questions. Graph Recall@5
was 0.925, hybrid 0.9083, and vector 0.8833. The corpus has 37 chunks, so these numbers do not
establish large-index performance or production generalization. Graph relationships establish
operational adjacency, not causality.

### CV-3 — Durable API and incident console

**Statement.** Delivered a FastAPI and React incident console with authenticated resumable SSE,
owner-scoped history, evidence and citation drill-down, metric and dependency views, durable report
review, cancellation, and versioned follow-ups.

**Implementation evidence.** `src/incidentgraph/api.py`, `src/incidentgraph/api_support.py`,
`src/incidentgraph/auth.py`, `src/incidentgraph/worker.py`, `frontend/src/App.tsx`, and
`frontend/src/api.ts`.

**Verification evidence.**
`tests/integration/test_phase7_api.py::test_real_api_report_evidence_sse_and_cross_user_boundaries`,
`frontend/e2e/investigation.spec.ts`, and the three sanitized images under
`artifacts/portfolio/`. The Playwright flow uses the real FastAPI/PostgreSQL lease, publication,
review, and resume path.

**Scope.** The screenshot/demo publisher is a clearly labeled deterministic test fixture with zero
model calls. It verifies the product flow, not diagnosis quality. Authentication and rate limiting
are local-development controls, not an enterprise identity boundary.

### CV-4 — Frozen evaluation and evidence quality

**Statement.** Built a sealed, resumable evaluation harness and completed 120 zero-paid-cost jobs
for a 30-case, 11-capture-group synthetic-lab holdout; the final v4 gate produced 20/20 Top-1 and
Top-3 diagnoses, 5/5 appropriate abstentions, 0/5 false incidents, 106/106 valid citations, and
69/69 supported reviewed claims.

**Implementation evidence.** `src/incidentgraph/phase9_v4_dataset.py`,
`src/incidentgraph/phase9_v4_evaluation.py`, `src/incidentgraph/phase9_v4_runner.py`,
`src/incidentgraph/phase9_repair.py`, `config/phase9-v4-fresh-freeze.json`, and
`phase9_v4_colab.ipynb`.

**Verification evidence.** `artifacts/evaluation/phase9-v4-fresh/aggregate.json`,
`artifacts/evaluation/phase9-v4-fresh/per-case.csv`,
`artifacts/evaluation/phase9-v4-fresh/manual-review.jsonl`, and
`artifacts/evaluation/phase9-v4-fresh/manual-review-summary.json`.

**Dataset and result scope.** The 30 variants share 11 project-authored captures. The 20 reviewed
reports represent seven capture groups. The review was AI-assisted, not independent human
validation. The local model controls bounded observation order; trusted pre-registered code owns
the v4 synthetic-lab diagnosis and citation content. These results are not a claim of autonomous
root-cause discovery in production.

### CV-5 — Reproducible local release

**Statement.** Containerized a loopback-only local release with non-root API/worker images,
standard and low-resource Compose profiles, frozen dependency installs, CI/security workflows,
checksum-backed PostgreSQL backup/restore, and an offline deterministic regression gate.

**Implementation evidence.** `Dockerfile`, `ops/compose.release.yaml`,
`ops/compose.low-resource.yaml`, `.github/workflows/ci.yml`,
`.github/workflows/security.yml`, `src/incidentgraph/release.py`, and
`docs/operations/RELEASE.md`.

**Verification evidence.** `docs/progress/phase-10-report.md` records an isolated clean-clone run:
150 offline backend tests, three frontend tests, one production frontend build, eight enabled
service integration tests, one real-API Playwright flow, PostgreSQL backup/restore with post-restore
smoke, and safe teardown.

**Scope.** The workflows are committed and syntax-checked but have not run on GitHub because no
push was authorized. The full dependency-heavy backend image build and Trivy image scan are
assigned to that remote workflow. This is a local containerized release, not a public deployment.

## Claims that must not be used

- Reduced a real organization's MTTR or prevented production incidents.
- Served thousands of users, achieved production reliability, or passed an enterprise audit.
- Proved causal root cause from graph relationships or correlated metrics.
- Built an autonomous remediation system; the product is intentionally read-only.
- Performed independent human validation; the written semantic review was AI-assisted.
- Worked professionally as an Agentic AI engineer solely because this personal project exists.
