# IncidentGraph

IncidentGraph is a production-inspired, evidence-grounded agent for investigating controlled infrastructure incidents. It is designed to combine an adaptive LangGraph workflow, LangChain model and tool contracts, Neo4j-backed graph-enhanced retrieval, durable PostgreSQL execution, and real laboratory telemetry.

## Current status

Phase 0 through Phase 8 are complete and passed. Phase 9 execution and error analysis are complete, with an honest **FAIL** gate result against the frozen quality targets. The versioned FastAPI surface and React console expose the durable investigator, while the hardened local runtime adds correlated API/worker/model/tool traces, bounded operational metrics, pre-export redaction, retention controls, adversarial tests, and a measured local resource snapshot. The Phase 5 and Phase 9 real-model evaluations used free Colab compute; no paid model call was made.

Roadmap progress: **10 of 12 gated phases have been decided: Phases 0–8 passed, Phase 9 failed its frozen quality gate, and Phases 10–11 have not started.**

See:

- [`docs/progress/phase-00-report.md`](docs/progress/phase-00-report.md)
- [`docs/progress/phase-01-report.md`](docs/progress/phase-01-report.md)
- [`docs/progress/phase-02-report.md`](docs/progress/phase-02-report.md)
- [`docs/progress/phase-03-report.md`](docs/progress/phase-03-report.md)
- [`docs/progress/phase-04-report.md`](docs/progress/phase-04-report.md)
- [`docs/progress/phase-05-report.md`](docs/progress/phase-05-report.md)
- [`docs/progress/phase-06-report.md`](docs/progress/phase-06-report.md)
- [`docs/progress/phase-07-report.md`](docs/progress/phase-07-report.md)
- [`docs/progress/phase-08-report.md`](docs/progress/phase-08-report.md)
- [`docs/progress/phase-09-report.md`](docs/progress/phase-09-report.md)
- [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md)
- [`docs/TASKS.md`](docs/TASKS.md)
- [`docs/HANDOFF.md`](docs/HANDOFF.md)

## Safety boundary

The investigator is read-only. It cannot execute remediation, control Docker, inject faults, generate arbitrary shell/Cypher/PromQL, or access production systems.

## Phase 1 quick start

Requirements: Docker Desktop, Node 24.13.1, npm 11.8.0, and `curl`. The bootstrap script installs project-local uv 0.12.17 and Python 3.12.14; it does not replace the system Python.

```bash
git clone https://github.com/mohammadrezakarami/incidentgraph.git
cd incidentgraph
./bootstrap.sh
cp .env.example .env
```

Replace every `CHANGE_ME` in `.env` with local-only URL-safe secrets. Generate a bearer token and hash with:

```bash
.tools/uv run incidentgraph generate-token
```

Store only the emitted SHA-256 hash in `INCIDENTGRAPH_AUTH_TOKENS_JSON`; keep the token itself outside Git. Each principal entry must also include an explicit non-empty `service_ids` list using canonical IDs such as `svc-gateway`, `svc-checkout`, or `svc-payments`. Then run:

```bash
make doctor
make up
make migrate
make smoke
make lint
make typecheck
make test
make test-integration
```

`make down` removes containers and the project network but intentionally preserves database volumes. Removing volumes is a separate destructive operation and is not part of the normal teardown.

## API surface

- `GET /health/live`
- `GET /health/ready`
- `POST /api/v1/investigations`
- `GET /api/v1/investigations`
- `GET /api/v1/investigations/{id}`
- `GET /api/v1/investigations/{id}/events`
- `GET /api/v1/investigations/{id}/report`
- `GET /api/v1/investigations/{id}/evidence/{evidence_id}`
- `POST /api/v1/investigations/{id}/reviews`
- `POST /api/v1/investigations/{id}/cancel`
- `POST /api/v1/investigations/{id}/followups`
- `GET /api/v1/services`
- `GET /api/v1/services/{id}/dependencies`
- `GET /metrics` (operator only)

Investigation endpoints require a configured bearer token and enforce owner scope or an explicit operator role. Review decisions additionally require a `reviewer` or `operator` role and are bound to a report version, expiry, reviewer identity, and idempotency key. SSE uses authenticated fetch streaming and `Last-Event-ID`; bearer tokens never enter URLs.

## Resource and cost boundary

The core and lab Compose services have explicit CPU and memory ceilings; Prometheus also has time and size retention. The optional Ollama profile remains off unless separately requested. No paid API or GPU workload is required for deterministic replay and security checks. Heavy evaluation work remains gated and will be moved to free Colab when appropriate.

## Phase 2 laboratory

Start the full local profile and run its integration checks with:

```bash
make lab-up
make test-lab-integration
make verify-captures
```

The real transaction path is:

```text
gateway -> checkout -> payments
               |          |  |
          lab PostgreSQL <-+  Redis
```

Prometheus scrapes each service every second. Each request produces bounded metrics, structured JSON logs, and W3C-propagated trace IDs. All published host ports bind to loopback.

Run one bounded scenario with, for example:

```bash
make scenario SCENARIO=downstream_latency
```

Supported fault families are `downstream_latency`, `pool_exhaustion`, `dependency_errors`, `cache_degradation`, `deployment_regression`, and `resource_contention`. Additional controls cover healthy traffic, healthy high traffic, misleading correlation, incomplete telemetry, and an ambiguous two-cause case.

Agent-readable captures are under `data/captures/`. Evaluator-only labels are under `data/evaluator/`, excluded from the Docker build context, and never mounted into a lab runtime container. The committed Phase 2 dataset contains 12 independent fault captures and five control captures. It is laboratory data, not production incident data.

Faults require a separate high-entropy operator token, expire automatically, are capped at 30 seconds, and can only affect the isolated lab. The services and investigator do not receive the Docker socket or fault-control token.

## Phase 3 knowledge graph and corpus

Apply the graph schema, load the reviewed topology, and incrementally ingest the corpus:

```bash
make seed
make ingest
make verify-ingestion
make benchmark-embeddings
```

The compact corpus contains 37 project-authored documents in `data/corpus/documents.json`, with one provenance record per document in `data/corpus/manifest.jsonl`. It includes service/API documentation, runbooks, configuration notes, link-oriented official reference summaries, reviewed synthetic development incidents, and explicit outdated/untrusted controls. It does not contain evaluator labels or held-out answers.

Neo4j stores three services, three resources, versioned relationships, deployments, reviewed synthetic incidents, documents, chunks, and normalized embeddings. `DEPENDS_ON` points from caller to callee; potential-impact traversal follows the reverse direction. Both the 384-dimensional cosine vector index and the full-text index are verified `ONLINE` before the corpus is marked searchable.

Embeddings use `sentence-transformers/all-MiniLM-L6-v2` at immutable revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, locally on CPU. The first model snapshot download is approximately 92 MB and is stored under ignored `models/`. The measured 37-chunk benchmark does not require Colab or a GPU.

## Phase 4 retrieval

All three retrieval variants use one typed, bounded interface and the same corpus snapshot, embedding revision, cutoff, authorization scope, and final context budget:

- `vector`: Neo4j cosine vector search.
- `hybrid`: vector and full-text candidate lists combined only by reciprocal-rank fusion.
- `graph`: hybrid retrieval over an authorization-filtered, time-valid `DEPENDS_ON` neighborhood of at most two hops and 50 nodes.

Try a graph-enhanced query:

```bash
make retrieve \
  VARIANT=graph \
  SERVICE=gateway \
  QUERY="Gateway latency rose while cache hits fell. Which downstream service should be investigated?"
```

Verify the sealed evaluation fixture and run only the development split:

```bash
make verify-retrieval
make test-retrieval-integration
make evaluate-retrieval-dev
```

The 40-question fixture contains 20 development and 20 held-out questions with disjoint groups. Evaluator labels remain under `data/evaluator/`; the held-out payload is SHA-256 sealed and was not evaluated in Phase 4. The committed development artifacts are under `artifacts/evaluation/phase4-dev/`.

## Phase 5 free Colab gate

The completed gate is reproducible with [`phase5_colab.ipynb`](phase5_colab.ipynb). It accepts a generated Git bundle without repository credentials, starts ephemeral Colab-local PostgreSQL and Ollama services, pulls `qwen3:4b-instruct-2507-q4_K_M`, runs deterministic checks and the two-case real-model gate, verifies that the held-out seal is unchanged, and downloads `gate-results.json`. The verified result is committed under `artifacts/evaluation/phase5-real-local/`; no paid API is configured or permitted.

## Phase 6 durable execution

Apply the third migration and run the lightweight durability gate with:

```bash
make migrate
make test-phase6-integration
```

The gate uses only the local PostgreSQL container and deterministic model fixtures. It covers expired-lease recovery, stale-worker fencing, idempotent publication and review decisions, process restart at a LangGraph review checkpoint, capacity release while waiting for a human, rejected stale/expired/unauthorized decisions, cooperative cancellation, and a budgeted follow-up that publishes report version 2. At-least-once delivery is assumed; externally visible effects are idempotent rather than described as exactly-once.

## Phase 7 API and incident console

The API and frontend run as separate local processes:

```bash
make api       # terminal 1
make worker    # terminal 2; requires an explicitly configured approved model
make frontend  # terminal 3, then open http://127.0.0.1:5173
```

The browser asks for the unhashed bearer token. It is sent only in the `Authorization` header and is not stored unless **Keep only for this browser tab** is selected. With the default `MODEL_PROVIDER=disabled`, existing records remain viewable but starting a new investigation returns a clean configuration error; the API never substitutes a fake model.

The console includes authorized history, LIVE/REPLAY and lifecycle states, resumable SSE, a bounded dependency graph, API-backed reports and citations, metric rendering, evidence provenance, human review, cancellation, and versioned follow-ups. Review acceptance explicitly does not execute recommendations or infrastructure changes.

The deterministic browser gate uses the real FastAPI/PostgreSQL queue and a clearly labeled fixture publisher, not a fake success route or an AI-quality claim:

```bash
make test-frontend
make test-e2e
```

Install the single Playwright browser once if it is not cached:

```bash
cd frontend && npx playwright install chromium
```

## Phase 8 observability and security

Application metrics are exposed only to an authenticated operator at `/metrics`. Optional local
tracing correlates API, durable worker, model, and read-only tool spans through a PostgreSQL-stored
W3C parent. It is disabled by default and, when enabled, writes redacted rotating JSONL under the
ignored `data/runtime/app-traces/` directory. No external collector is required.

Run the deterministic hardening gate and preview event retention:

```bash
RUN_INTEGRATION=1 .venv/bin/pytest tests/integration/test_phase8_hardening.py -v
make retention-status
```

The security suite rejects injected shell-like fields and unauthorized service expansion, samples
traces for secrets, and proves dependency errors fail closed. The lightweight resource snapshot is
reproducible with `.venv/bin/python scripts/phase8_profile.py`; it is not a capacity benchmark.
See [`docs/operations/OBSERVABILITY.md`](docs/operations/OBSERVABILITY.md) and
[`docs/security/SECURITY_TESTS.md`](docs/security/SECURITY_TESTS.md).

## Phase 9 frozen evaluation

The prompts, workflow, evaluator, datasets, seals, corpus snapshot, dependency lock, exact local
Qwen digest, scoring rules, targets, and zero-paid-cost budget are frozen in
[`config/phase9-freeze-v1.json`](config/phase9-freeze-v1.json). Verify them without running a model:

```bash
make verify-phase9-freeze
```

The heavy 120-job agent comparison is intentionally not a local Make workload. Use
[`phase9_colab.ipynb`](phase9_colab.ipynb) with the matching
`incidentgraph-phase9-colab.bundle` on a free T4. It runs 12 resumable shards of 10 jobs, carries
progress between sessions as `phase9-progress.zip`, and never configures a paid provider. The
comparison includes fixed versus adaptive workflows, three repeats of the frozen 10-case
development subset, one run over all 30 held-out cases, and the 20-question three-variant held-out
retrieval benchmark.

The returned zero-cost run completed all 120 agent jobs. Its aggregate and per-case hashes reproduced
exactly, and the written claim-support review covers 20 actual reports. The frozen gate failed:
graph Recall@5 passed at 0.925, but adaptive diagnosis Top 1 and Top 3 were both 0/20, citation
validity was 77/78, warm p95 was 280.463 seconds, three blocked policy-violation attempts were
recorded, coverage remained below target, and supported factual claims were 32/57 (56.1%). See the
committed artifacts under `artifacts/evaluation/phase9-frozen-v1/`. The semantic review is explicitly
AI-assisted and is not represented as independent human validation.

The original v1 result remains immutable. A separately frozen corrective regression is available in
[`config/phase9-v2-regression-freeze.json`](config/phase9-v2-regression-freeze.json) and
[`phase9_v2_colab.ipynb`](phase9_v2_colab.ipynb). It fixes the context overflow, constructs canonical
tool arguments in trusted code, presents explicit metric semantics, bounds the adaptive LangGraph to
named observation bundles, and rejects unsupported citations. Verify it with
`make verify-phase9-v2-freeze`. Its 120-job model run remains free-Colab-only and is explicitly a
regression over the now-consumed v1 cases—not a replacement held-out claim. The later v3 iteration
supplied the required fresh post-corpus suite and 20-report written rubric, but it still failed the
unchanged quality targets.

The separately versioned Phase 9 v3 path supplies that fresh surface: 22 post-corpus captures,
disjoint capture groups between development and held-out splits, a sealed 60-case dataset, and
trusted normalization of bounded lab signals. Verify it with `make verify-phase9-v3-freeze`; the
real-model run was completed through `phase9_v3_colab.ipynb` on a free T4 and never authorized a
paid provider. All 120 jobs completed and the returned aggregate reproduced byte-for-byte. The
fresh v3 gate also failed: adaptive Top 1/Top 3 were 0/20, abstention was 3/5, false incidents were
0/5, task completion was 30/30, and the 20-report written rubric found 0/20 supported factual
conclusions. Complete artifacts are under `artifacts/evaluation/phase9-v3-fresh/`.
