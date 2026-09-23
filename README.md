# IncidentGraph

IncidentGraph is a production-inspired, evidence-grounded agent for investigating controlled infrastructure incidents. It is designed to combine an adaptive LangGraph workflow, LangChain model and tool contracts, Neo4j-backed graph-enhanced retrieval, durable PostgreSQL execution, and real laboratory telemetry.

## Current status

Phase 0 through Phase 3 are complete. The repository now includes the reproducible foundation, working three-service telemetry lab, immutable incident captures, a versioned Neo4j operational graph, and an incrementally ingested provenance-aware corpus with local embeddings. No AI investigator, retrieval comparison, or production capability is claimed yet.

Roadmap progress: **Phase 3 of 11 delivery phases is complete; 4 of 12 gated phases are complete when discovery Phase 0 is included. Eight phases remain.**

See:

- [`docs/progress/phase-00-report.md`](docs/progress/phase-00-report.md)
- [`docs/progress/phase-01-report.md`](docs/progress/phase-01-report.md)
- [`docs/progress/phase-02-report.md`](docs/progress/phase-02-report.md)
- [`docs/progress/phase-03-report.md`](docs/progress/phase-03-report.md)
- [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md)
- [`docs/TASKS.md`](docs/TASKS.md)
- [`docs/HANDOFF.md`](docs/HANDOFF.md)

## Safety boundary

The planned agent is read-only. It will not execute remediation, control Docker, inject faults, generate arbitrary shell/Cypher/PromQL, or access production systems.

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

Store only the emitted SHA-256 hash in `INCIDENTGRAPH_AUTH_TOKENS_JSON`; keep the token itself outside Git. Then run:

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

## Phase 1 API surface

- `GET /health/live`
- `GET /health/ready`
- `POST /api/v1/investigations`
- `GET /api/v1/investigations/{id}`
- `GET /api/v1/investigations/{id}/events`

Investigation endpoints require a configured bearer token. Submitted investigations currently enqueue an explicitly non-AI durability test job; they do not run an investigator.

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

Faults require a separate high-entropy operator token, expire automatically, are capped at 30 seconds, and can only affect the isolated lab. The services do not receive the Docker socket and the future agent will not receive the fault-control token.

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
