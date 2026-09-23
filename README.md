# IncidentGraph

IncidentGraph is a production-inspired, evidence-grounded agent for investigating controlled infrastructure incidents. It is designed to combine an adaptive LangGraph workflow, LangChain model and tool contracts, Neo4j-backed graph-enhanced retrieval, durable PostgreSQL execution, and real laboratory telemetry.

## Current status

Phase 0 through Phase 7 are complete. The versioned FastAPI surface and React incident console now expose the durable investigator with authorized history, resumable event streaming, reports, evidence drill-down, metric charts, time-aware dependencies, review, cancellation, and follow-ups. The Phase 5 real-model gate used free Colab compute; Phases 6 and 7 used only deterministic fixtures, PostgreSQL, and one local browser test. No paid model call was made.

Roadmap progress: **Phase 7 of 11 delivery phases is complete; 8 of 12 gated phases are complete when discovery Phase 0 is included, and Phases 8–11 have not started.**

See:

- [`docs/progress/phase-00-report.md`](docs/progress/phase-00-report.md)
- [`docs/progress/phase-01-report.md`](docs/progress/phase-01-report.md)
- [`docs/progress/phase-02-report.md`](docs/progress/phase-02-report.md)
- [`docs/progress/phase-03-report.md`](docs/progress/phase-03-report.md)
- [`docs/progress/phase-04-report.md`](docs/progress/phase-04-report.md)
- [`docs/progress/phase-05-report.md`](docs/progress/phase-05-report.md)
- [`docs/progress/phase-06-report.md`](docs/progress/phase-06-report.md)
- [`docs/progress/phase-07-report.md`](docs/progress/phase-07-report.md)
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

The Phase 1 Compose profile limits the two PostgreSQL containers and Neo4j to 2.75 GiB aggregate configured memory. No model, embedding, dataset, paid API, or GPU workload is used. Heavy capture/evaluation work remains gated in later phases and will be identified before it is run.

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
