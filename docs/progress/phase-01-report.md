# PHASE 1 REPORT — Reproducible Foundation and Contracts

Status: PASS

Date: 2026-09-22

## 1. Objective and result

Phase 1 established a reproducible, compact project foundation without implementing or claiming an AI investigator. The repository now has locked Python and Node environments, typed configuration, static and unit checks, digest-pinned ARM64 container services, application migrations, structured JSON logging, a thin authenticated FastAPI surface, typed domain contracts, and a PostgreSQL-backed queue/event slice for an explicitly non-AI test job.

The phase gate passes. A clean clone bootstrapped project-local uv 0.12.17 and Python 3.12.14 from the committed lockfile. PostgreSQL 18.6 and Neo4j 2026.09.0 passed real connectivity checks. Normal Compose teardown preserved persisted data. Missing configuration produced explicit validation errors. Nine unit tests passed, a real HTTP request without credentials returned 401, and the integration test proved that an expired worker lease is reclaimed while the stale worker is fenced from completion.

No dataset, embedding model, chat model, paid API, or GPU workload was used. The controlled lab and its incident captures begin in Phase 2; a curated corpus and retrieval data begin in Phase 3.

## 2. Implemented changes

- `bootstrap.sh`, `.python-version`, `pyproject.toml`, and `uv.lock`: pinned project-local bootstrap and exact Python dependency resolution.
- `frontend/package.json` and `frontend/package-lock.json`: pinned Node 24.13.1/npm 11.8.0 runtime contract. React is intentionally deferred until the console phase.
- `.env.example` and `incidentgraph.config`: typed configuration, clear validation, loopback-only Phase 1 binding, disabled-by-default model provider, and explicit budget fields.
- `ops/compose.yaml`: two isolated PostgreSQL services and Neo4j with loopback ports, health checks, persistent volumes, resource limits, exact tags, and ARM64-tested digests.
- `ops/migrations/001_app.sql`: separate application/checkpoint schemas, investigations, jobs, events, constraints, indexes, and migration record.
- `incidentgraph.persistence`: transactional enqueue, idempotency key, event sequencing, short job claim, lease, heartbeat, retry attempt, and lease-token fencing.
- `incidentgraph.auth`: SHA-256 token hashes and constant-time bearer-token comparison. Plaintext tokens are not committed.
- `incidentgraph.api`: liveness/readiness and initial investigation/event endpoints with ownership-scoped repository calls.
- `incidentgraph.worker`: one-shot explicitly non-AI worker path.
- `incidentgraph.logging`: structured JSON logging foundation.
- `incidentgraph.models`: initial request, investigation, event, lease, evidence, and error contracts.
- `tests/unit` and `tests/integration`: configuration, validation, auth, API, and real durable-recovery checks.
- `Makefile` and `README.md`: repeatable operator commands and honest phase boundary.

The repository remains compact: one Python package, one migration directory, one frontend directory, categorized tests, and the existing documentation tree. No empty architecture-mirroring directories were added.

## 3. Engineering decisions and tradeoffs

### Durable delivery is separate from workflow state

The Phase 1 queue owns job delivery and lease fencing. The checkpoint schema is reserved separately, but LangGraph checkpoint tables are not initialized or claimed as functional before the graph lifecycle exists. This keeps the scheduler/checkpointer boundary explicit.

Delivery semantics are at-least-once. An idempotency key prevents duplicate request creation, one job exists per investigation, and a lease token prevents a stale worker from completing after ownership has moved. Exactly-once execution is not claimed.

### Basic authentication is intentionally small

The local API accepts high-entropy bearer tokens configured by SHA-256 hash. Comparison is constant-time, ports bind to loopback, and object reads include an owner ID. This is a development boundary, not enterprise identity, multi-tenant SaaS, or production authorization.

### Coverage enforcement remains visible, not falsified

`make coverage` retains the specification's 85 percent threshold. The current unit-only measurement is 51.09 percent over all foundation modules and therefore fails that separate command. Phase 1 requires that unit checks run and pass; the 85 percent target applies to the later core domain, policy, retrieval, and orchestration implementation. The threshold was not lowered and the result is not presented as passing.

### Reproducibility and resources

uv and Python install under `.tools`; system Python is unchanged. Container tags are paired with pulled ARM64 digests. The Phase 1 Compose limits total 2.75 GiB, while observed idle use was approximately 586 MiB across the three services. No Colab run is needed for this phase.

## 4. Verification evidence

| Check | Result | Evidence |
|---|---|---|
| Clean bootstrap | PASS | Clean local clone downloaded uv 0.12.17 and Python 3.12.14; 85 locked packages installed; npm audit reported zero vulnerabilities |
| Clean static/unit checks | PASS | Ruff passed; strict mypy passed 10 source files; 9 unit tests passed |
| Dependency compatibility | PASS | Imports for LangChain tools, LangGraph `StateGraph`, PostgreSQL checkpointer, and Neo4j GraphRAG retriever succeeded |
| Container compatibility | PASS | PostgreSQL and Neo4j versioned/digest-pinned images run on Linux/ARM64 and report healthy |
| Real store connectivity | PASS | `{"postgres": true, "neo4j": true}` |
| Migration | PASS | `001_app.sql` applied to real PostgreSQL and can be reapplied idempotently |
| Safe teardown | PASS | Investigation count was 1 before `docker compose down`, remained 1 after `up`; no volume deletion occurred |
| Configuration failure | PASS | Running `incidentgraph doctor` without `.env` exited 2 and named all four missing required settings |
| Valid configuration | PASS | `make doctor` returned status `ok`, loopback bind, model provider `disabled`, and no problems |
| Unauthorized HTTP | PASS | Real Uvicorn request without bearer credentials returned `HTTP/1.1 401 Unauthorized` |
| Controlled worker recovery | PASS | Real PostgreSQL integration test: expired attempt reclaimed as attempt 2, one completion event, stale completion rejected |
| Unit-only global coverage | FAIL / future target | 51.09 percent versus retained 85 percent threshold; not a Phase 1 gate and not claimed complete |

Selected resolved versions:

| Component | Locked/tested version |
|---|---:|
| Python | 3.12.14 |
| uv | 0.12.17 |
| FastAPI / Pydantic | 0.141.1 / 2.13.5 |
| LangChain / LangGraph | 1.4.2 / 1.2.11 |
| LangGraph PostgreSQL checkpoint package | 3.1.2 |
| Neo4j driver / GraphRAG | 6.3.1 / 1.19.0 |
| psycopg / psycopg-pool | 3.3.6 / 3.3.2 |
| PostgreSQL image | 18.6-bookworm, ARM64 digest pinned |
| Neo4j image | 2026.09.0, ARM64 digest pinned |
| Node / npm | 24.13.1 / 11.8.0 |

Observed idle container use after startup:

| Service | Memory / configured limit | CPU sample |
|---|---:|---:|
| app PostgreSQL | 25.49 MiB / 768 MiB | 0.66% |
| lab PostgreSQL | 24.92 MiB / 512 MiB | 3.29% |
| Neo4j | 535.7 MiB / 1.5 GiB | 1.31% |

These are single idle samples, not capacity results.

## 5. Phase 1 acceptance checklist

| Gate criterion | Result | Qualification |
|---|---|---|
| Fresh setup works | PASS | Clean clone bootstrap and clean static/unit checks passed |
| Teardown does not delete data | PASS | `down`/`up` preserved the real PostgreSQL record and named volumes |
| PostgreSQL connectivity | PASS | Real driver connection and migration passed |
| Neo4j connectivity | PASS | Official async driver connectivity verification passed |
| Configuration errors are clear | PASS | Missing fields named, exit status 2 |
| Unit checks run | PASS | 9 passed, 1 integration test deselected by category |
| Unauthorized requests fail | PASS | TestClient and real Uvicorn request both returned 401 |
| Test job survives controlled worker restart | PASS | Lease-expiry/reclaim/fencing integration test passed |
| No placeholder is called an investigator | PASS | README/API explicitly label the current job as non-AI foundation work |

## 6. How to try it

Follow the quick start in `README.md`. With a configured `.env`:

```bash
./bootstrap.sh
make doctor
make up
make migrate
make smoke
make test
make test-integration
```

Normal cleanup is:

```bash
make down
```

This intentionally preserves data volumes.

## 7. Limitations and risks

- The current API is a contract/durability slice. It does not investigate telemetry or generate a report.
- The checkpoint namespace and dependency are present, but actual LangGraph checkpoint setup belongs with the workflow implementation.
- Token auth is appropriate only for the bounded local release.
- Coverage is below the later 85 percent core target; the retained coverage command exposes this failure.
- The Starlette test client emits an upstream AnyIO deprecation warning; tests still pass.
- GitHub CLI authentication is stale, although the private remote exists and browser authentication created it.
- Provider access and monetary budget remain unapproved and are not required until the real-model gate.

## 8. What the user should understand

The key safety mechanism is the lease token. A worker does not gain permanent authority merely because it once claimed a row. Every state-changing completion checks the current owner, current token, running status, and unexpired lease. After recovery, the old worker's token is stale and its completion is rejected.

Interview question: Why not use a FastAPI background task?

Answer: a background task is coupled to the API process and does not provide durable claiming, restart recovery, retry accounting, or stale-worker fencing. PostgreSQL persists the delivery state independently of API/worker lifetimes.

## 9. Next phase

Phase 2 will build the isolated transaction lab, telemetry, bounded workload and fault controller, six fault families, healthy controls, cleanup, and real capture artifacts. It must not begin until the user approves Phase 2.

No Colab work is currently required. If a later capture/evaluation operation is expected to be computationally heavy or exceed the local resource policy, it will be stopped and handed to the user with an exact Colab procedure before execution.

## 10. Resume state

- Phase 1 status: PASS.
- Runtime: Docker Desktop and the three Phase 1 services are running and healthy.
- Data: named volumes are present; one integration investigation remains in the application database.
- Git: implementation commit `13efd97` on `main`; continuity/report changes follow in the phase-close commit.
- Remote: private `https://github.com/mohammadrezakarami/incidentgraph`.
- Exact next action: wait for explicit Phase 2 approval, then define the minimal three-service lab contracts before adding containers.
