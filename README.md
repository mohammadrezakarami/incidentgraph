# IncidentGraph

IncidentGraph is a production-inspired, evidence-grounded agent for investigating controlled infrastructure incidents. It is designed to combine an adaptive LangGraph workflow, LangChain model and tool contracts, Neo4j-backed graph-enhanced retrieval, durable PostgreSQL execution, and real laboratory telemetry.

## Current status

Phase 0 and Phase 1 are complete. The repository now has a reproducible Python/Node foundation, typed contracts, a thin authenticated API, and a PostgreSQL-backed non-AI queue/event slice. PostgreSQL and Neo4j run locally through Docker Compose. No AI investigator, retrieval benchmark, or production capability is claimed yet.

See:

- [`docs/progress/phase-00-report.md`](docs/progress/phase-00-report.md)
- [`docs/progress/phase-01-report.md`](docs/progress/phase-01-report.md)
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
