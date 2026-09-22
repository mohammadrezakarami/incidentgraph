# PHASE 0 REPORT — Discovery, Architecture, and Feasibility

Status: PASS

Date: 2026-09-22

## 1. Objective and result

Phase 0 was limited to discovery and design. The workspace, host, local tooling, credential presence, official compatibility information, dataset options, resource constraints, trust boundaries, and implementation risks were inspected. No application code, dependency installation, model download, container pull, paid model call, or benchmark run was performed.

The proposed design is feasible on the inspected Apple Silicon laptop if the core Compose profile is kept below an aggregate container budget of approximately 6.5 GiB and optional observability services are not enabled by default. The design deliberately uses one investigator, one backend codebase, one worker, two isolated PostgreSQL services, Neo4j Community, Prometheus, a small Redis instance, and three lightweight lab services.

The phase gate passes because every mandatory technology has a concrete role, the local resource plan is plausible, current edition/API assumptions were checked against first-party documentation, and every unverified item is listed explicitly. Runtime compatibility remains a Phase 1 acceptance requirement because the Docker daemon was not running and the required Python/uv toolchain is not installed.

## 2. Implemented changes

Only planning and continuity documents were added:

- `docs/progress/phase-00-report.md`: complete discovery and implementation plan.
- `docs/PROJECT_STATUS.md`: current status and verified facts.
- `docs/TASKS.md`: phase checklist and decision gates.
- `docs/HANDOFF.md`: exact resume state.
- `docs/adr/0001-single-investigator.md`: one adaptive investigator.
- `docs/adr/0002-neo4j-graph-and-vectors.md`: Neo4j for topology and retrieval indexes.
- `docs/adr/0003-postgresql-durable-execution.md`: durable queue, events, and checkpoints.
- `docs/adr/0004-replay-isolation.md`: immutable replay boundaries.
- `docs/adr/0005-read-only-operational-scope.md`: read-only tools and no remediation execution.

No repository was initialized inside `incidentgraph`, no commit was made, and no unrelated workspace file was changed.

## 3. Decisions and tradeoffs

### Product boundary

Core scope remains the specification's complete local portfolio release: instrumented lab, six fault families, live and replay modes, versioned graph/corpus, three retrievers, adaptive LangGraph investigator, durable review/resume, API, console, security tests, and reproducible evaluation.

Deferred extensions remain out of scope: multiple agents, remediation execution, Kubernetes, a second vector database, model training/fine-tuning, public deployment, and production-system access. OpenRCA and AIOpsLab are useful external references or later portability tests, but they are not the core dataset or runtime. OpenRCA's documented recommendation of at least 32 GiB RAM and 80 GiB storage makes it unsuitable for the inspected laptop as a core dependency.

### Minimal repository layout

To avoid excessive directory nesting, create directories only when the corresponding implementation lands:

```text
incidentgraph/
  backend/incidentgraph/   # initially cohesive modules; split only when warranted
  frontend/                # React/Vite console
  lab/                     # three services, load generator, fault controller
  ops/                     # Compose, telemetry, migrations, operational configuration
  config/                  # reviewed query/model/budget templates
  prompts/                 # versioned prompts
  data/                    # corpus and evaluation manifests/small fixtures
  tests/                   # categorized test suites
  docs/                    # ADRs, progress, security, portfolio documentation
  artifacts/               # generated, sanitized local artifacts
```

The specification's logical boundaries will still exist as Python modules and documented contracts. Empty directories and one-file packages will not be created merely to mirror the suggested tree.

### Smallest compliant architecture

```text
Browser
  -> FastAPI (auth, validation, SSE, thin routes)
       -> application PostgreSQL (requests, queue, leases, events, evidence,
                                  reports, reviews, LangGraph checkpoints)
       -> Worker (same backend image; one active investigation)
            -> LangGraph investigator
                 -> reviewed read-only adapters
                      -> Neo4j (topology, documents, vector/full-text indexes)
                      -> Prometheus (bounded query templates)
                      -> bounded structured-log volume
                      -> deployment/change records
                 -> hosted chat model through LangChain

Lab control plane (operator only)
  -> gateway -> checkout -> payments
                    |          |
                 lab PostgreSQL Redis
  -> Prometheus + bounded logs + OpenTelemetry

Capture tool -> immutable replay snapshot -> same read-only adapter contracts
Evaluator-only labels are outside API/worker mounts and image contexts.
```

API and worker share one image and domain code but run as separate processes. The lab services may share one small image while running as separate containers. This preserves observable boundaries without creating separate repositories or unnecessary distributed infrastructure.

### Trust boundaries

1. Browser input is untrusted and cannot choose checkpoint IDs, principal scope, query text, or internal endpoints.
2. API authenticates high-entropy development bearer tokens stored as hashes and enforces per-object ownership.
3. Worker leases are fenced; a stale attempt cannot append events or publish a report.
4. LLM, corpus, logs, and tool outputs are untrusted. Policy enforcement, budgets, numerical calculations, and query construction are deterministic.
5. Neo4j and Prometheus adapters expose reviewed templates only. The model never emits executable Cypher, PromQL, shell, URLs, or filesystem paths.
6. Fault controls are loopback/internal-only, time-limited, and unavailable to the agent.
7. Replay snapshots are immutable and cutoff-bound. Evaluator labels are not mounted into the runtime.
8. External model and tracing providers are disabled until explicitly configured and approved.

### ADR summary

- ADR-0001: use one adaptive investigator, not a multi-agent team.
- ADR-0002: use Neo4j Community for both graph relations and document indexes.
- ADR-0003: use application PostgreSQL for queue/events/reviews and a supported PostgreSQL LangGraph checkpointer; keep scheduler and checkpoint responsibilities distinct.
- ADR-0004: route LIVE and REPLAY through the same typed interfaces while strictly isolating immutable replay data by cutoff.
- ADR-0005: permit read-only investigation only; report acceptance does not authorize action execution.

## 4. Verification evidence

### Commands executed

| Check | Result | Exit status / evidence |
|---|---|---|
| Workspace file and instruction scan | No `AGENTS.md`; many unrelated sibling projects; no pre-existing IncidentGraph code | `rg`, `find`; exit 0 |
| Parent Git status | Branch `main`, no commits, many unrelated untracked files | `git status`, exit 0; `git log`, exit 128 because no commit exists |
| Host OS/architecture | macOS 26.6.2, ARM64, Apple M4, 10 cores, 16 GiB RAM | `uname`, `sw_vers`, `system_profiler`; inspection only |
| Storage | Approximately 95 GiB free on the data volume | `df -h`; inspection only |
| Python | Host default is Python 3.14.2, not required Python 3.12 | version check; exit 0 |
| uv | Missing | command availability check; exit 0 with explicit `missing` result |
| Node/npm | Node v24.13.1 and npm 11.8.0 installed | version check; exit 0 |
| Docker client/Compose | Docker 29.4.1 and Compose v5.1.3 installed | version check |
| Docker engine | Not running or unavailable; no container probe was possible | `docker version`; exit 1 |
| Relevant credential variables | No matching provider/database API-key environment variable names found; values were never requested or printed | environment-name-only scan; exit 0 |

### Official compatibility evidence checked

- Node 24 is an active LTS line through April 2028: https://nodejs.org/en/about/previous-releases
- Neo4j supports ARM64 development environments; current documentation identifies Neo4j 2026.09.0 and official versioned Community images: https://neo4j.com/docs/operations-manual/current/installation/requirements/ and https://neo4j.com/docs/operations-manual/current/docker/introduction/
- PostgreSQL 18.6 is a supported current release: https://www.postgresql.org/support/versioning/
- Python 3.12.14 is the current security release in the required 3.12 line; the line is supported for security fixes through October 2028: https://www.python.org/downloads/release/python-31213/
- Current package metadata observed: LangChain 1.4.2, LangGraph 1.2.11, `langgraph-checkpoint-postgres` 3.1.2, `langchain-openai` 1.6.x, and Neo4j GraphRAG 1.19.0. Exact compatible pins must be resolved together into `uv.lock`, not copied independently from latest-version pages.
- Neo4j GraphRAG 1.19.0 declares Python 3.12 support: https://pypi.org/project/neo4j-graphrag/
- LangChain's OpenAI integration supports the Responses API, tool calling, and Pydantic/JSON-schema structured output: https://reference.langchain.com/python/langchain-openai/langchain_openai and https://reference.langchain.com/python/langchain-openai/chat_models/base/BaseChatOpenAI/with_structured_output
- OpenAI's GPT-5.4 Mini model page documents function calling, structured outputs, a versioned snapshot, and current token prices: https://developers.openai.com/api/docs/models/gpt-5.4-mini
- The proposed local embedding model card documents 384-dimensional embeddings and Apache-2.0 licensing: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2

No unit, integration, replay, live-service, browser, or real-LLM tests were run. No mocks were run. No package combination has yet been installed together.

## 5. Acceptance checklist

| Phase 0 criterion | Result | Evidence / qualification |
|---|---|---|
| Inspect repository and instructions | PASS | No IncidentGraph code or `AGENTS.md`; parent directory contains unrelated work |
| Inspect hardware and tools | PASS | Apple M4/16 GiB; versions recorded above |
| Concrete role for every required technology | PASS | Architecture and responsibility mapping below |
| Smallest core architecture defined | PASS | Single modular backend, one worker, one frontend, bounded lab |
| Edition/API assumptions checked | PASS | First-party documentation checked; runtime pull/probe remains pending |
| Plausible local resource plan | PASS | Budget below; not yet measured |
| Model/provider proposal and cost gate | PASS | Proposal documented; provider and spend remain unapproved |
| Dataset/evaluation plan | PASS | Controlled captures plus transparent transformed/synthetic cases |
| Five required ADRs written | PASS | `docs/adr/0001` through `0005` |
| Node LTS/package manager selected | PASS | Node 24, npm 11; lockfile to be created with frontend in Phase 1 |
| Python dependency lockfile generated | NOT RUN | `uv` missing; Docker daemon unavailable; defer to Phase 1 compatibility probe |
| Container compatibility probe | NOT RUN | Docker daemon is not running |
| Paid model call | NOT RUN | No key detected and no budget approval |

## Appendix A — Proposed implementation plan

### Technology responsibility and preliminary compatibility matrix

| Component | Proposed selection | Concrete role | Status |
|---|---|---|---|
| Python | 3.12.14 container/toolchain | Backend, worker, lab, evaluation | Required line verified; local runtime not installed |
| Package manager | uv, exact version pinned at bootstrap | Resolve and lock all Python dependencies | Missing locally |
| LangChain | 1.4.x candidate | Model invocation, typed tools, structured responses | Package metadata checked; joint lock pending |
| LangGraph | 1.2.11 candidate | Explicit state graph, loops, interrupt/resume | Package metadata checked; joint lock pending |
| LangGraph PostgreSQL checkpointer | 3.1.2 candidate | Persistent workflow checkpoints | Python requirement checked; live setup pending |
| Model adapter | `langchain-openai` 1.6.x candidate | Hosted model integration behind an internal protocol | Features checked; real call unapproved |
| Neo4j | Community 2026.09.0 candidate | Versioned topology, documents, vector/full-text indexes | ARM64 and official image documented; pull pending |
| Neo4j driver / GraphRAG | Official driver resolved with `neo4j-graphrag` 1.19.0 | Parameterized Cypher and optional retriever primitives | Python 3.12 support checked; API spike pending |
| PostgreSQL | 18.6 candidate, two isolated containers | Durable app state/checkpoints and isolated lab DB | Supported release checked; container probe pending |
| FastAPI/Pydantic | Current mutually resolved stable versions | REST/SSE and boundary schemas | Exact pins pending joint lock |
| Prometheus | Versioned current image selected during lock step | Metrics store and bounded range queries | API design known; exact image digest pending |
| OpenTelemetry | Python SDK/exporter versions resolved together | Correlated spans and trace context | Exact pins pending joint lock |
| Redis | Versioned official image | Real cache dependency and cache-degradation scenario only | Exact image digest pending |
| Frontend | React + TypeScript + Vite | Incident console | Exact versions pending frontend lock |
| Node/package manager | Node 24.13.1 + npm 11.8.0 | Reproducible frontend build | Installed and Node LTS status verified |
| Graph UI | `@xyflow/react` candidate | Bounded service dependency view only | API/bundle-size probe pending |
| Local embeddings | `sentence-transformers/all-MiniLM-L6-v2`, exact Hub revision pinned in Phase 3 | 384-dimension offline document embeddings | License/dimension checked; CPU benchmark pending |
| Hosted chat model | OpenAI `gpt-5.4-mini-2026-03-17` candidate via Responses API | Adaptive planning, hypothesis updates, report drafting | Features/pricing documented; account availability and budget unverified |

Candidate versions are not lockfile claims. Phase 1 must use uv's resolver, run import/schema probes, and save the resolved versions and image digests. Floating `latest` tags are prohibited.

### Model and budget proposal

Use a provider-neutral `ChatModelPort` in domain code. Configure OpenAI only through the LangChain provider adapter. The first proposed real model is the versioned `gpt-5.4-mini-2026-03-17` snapshot because the official model page documents function calling and structured outputs and presents it as a faster, lower-cost mini model. Start with low reasoning effort, sequential tool calls, server-side budget checks, and no provider-side storage unless explicitly required and approved.

This is a proposal, not authorization. No paid calls occur until the user approves the provider and two explicit ceilings:

1. Real-model smoke ceiling for Phase 5 (suggested starting ceiling: EUR 5 equivalent).
2. Development and held-out evaluation ceilings for Phase 9, approved separately after actual per-case usage is measured.

Official listed GPT-5.4 Mini text pricing observed on 2026-09-22 was USD 0.75 per million input tokens, USD 0.075 per million cached input tokens, and USD 4.50 per million output tokens. Account availability, taxes, currency conversion, rate limits, and future prices are unverified; cost controls must use current provider-reported usage and a conservative configured ceiling.

### Dataset plan

There is no need to depend on a ready-made dataset. The core evidence collection will be purpose-built and reproducible:

- At least 12 independent live captures: two separately executed captures for each of the six fault families.
- Separate healthy, incomplete-telemetry, misleading-correlation, and ambiguous two-cause captures.
- Sixty incident cases with group-aware 30/30 development/holdout splits. Independent captures remain distinct; parameterized variants are labeled `transformed_capture` or `synthetic_fixture`, never presented as independent production incidents.
- Forty retrieval questions with annotated document/evidence paths and a sealed 20/20 split.
- Thirty to fifty curated project documents with temporal/provenance metadata.

Public datasets can be used only as later external-validity extensions. Microsoft OpenRCA is relevant but too resource-heavy for the local core and uses a different telemetry/task contract. AIOpsLab requires a Kubernetes/Helm-oriented environment that conflicts with the intentionally small Docker Compose core. The OpenTelemetry Demo is a useful instrumentation reference, but its large polyglot system is unnecessary for this project's three-service lab.

### Evaluation protocol before tuning

1. Define schemas, answerability labels, component/mechanism taxonomy, grouping rules, scoring code, and evaluator-only mount exclusions before prompt tuning.
2. Create development and holdout manifests at case creation time; hash and seal retrieval holdout before Phase 4 tuning and incident holdout before Phase 5 tuning.
3. Compare vector, hybrid, and graph-enhanced retrieval with identical corpus snapshot, eligibility rules, embeddings, and context budget.
4. Compare fixed workflow and adaptive investigator with identical tools, graph-enhanced retriever, observations, generator model, and upper resource limits.
5. Record per-case calls, latency, tokens, cost, evidence IDs, and errors. Compute aggregates from saved case artifacts only.
6. Perform group-level uncertainty analysis where sample size permits and manually review at least 20 reports with the written support rubric.
7. Treat targets as targets; never rewrite thresholds after results are known.

### Requirements-to-test mapping seed

| Requirement | Planned evidence |
|---|---|
| Durable queue and checkpoint boundary | PostgreSQL integration and worker kill/restart tests |
| At most one active execution | Unique lease/fencing integration tests |
| Six real fault families | Scenario acceptance scripts plus captured telemetry/recovery checks |
| Live/replay equivalence | Adapter contract tests over paired observations |
| Temporal graph/corpus eligibility | Neo4j integration and property/table-driven tests |
| Three retriever comparison | Frozen question manifest and executable retrieval scorer |
| Adaptive behavior | Deterministic routing tests plus at least two real-model traces with different next-tool choices |
| Grounded reports | Citation resolution/numeric consistency checks and human support rubric |
| Human review semantics | Interrupt/resume, stale decision, idempotency, and authorization tests |
| API ownership/SSE resume | Contract/integration tests and Playwright reconnect/cross-user tests |
| Prompt-injection containment | Threat-model security tests proving deterministic tool denial |
| Evaluation leakage isolation | Image/volume manifest tests and runtime path assertions |

### Phase estimates and dependencies

Estimates are engineering ranges for one person and include debugging/documentation; they are not delivery promises.

| Phase | Focus | Estimate | Main dependency |
|---|---|---:|---|
| 1 | Foundation, locks, Compose, schemas, queue | 4–7 focused days | Docker daemon, internet for first pull |
| 2 | Lab, telemetry, faults, captures | 7–12 days | Phase 1 data stores and tracing |
| 3 | Graph, corpus, ingestion | 5–8 days | Stable service topology and corpus drafts |
| 4 | Three retrievers and dev retrieval evaluation | 4–7 days | Phase 3 indexes and sealed questions |
| 5 | Adaptive investigator and reports | 7–12 days | Provider/budget approval for real smoke |
| 6 | Recovery, review, follow-ups | 5–8 days | Working persistent graph and queue |
| 7 | Full API and console | 6–10 days | Stable domain/API contracts |
| 8 | Observability/security hardening | 5–8 days | End-to-end path available |
| 9 | Frozen evaluation/error analysis | 5–10 days elapsed | Sealed holdout and separate budget approval |
| 10 | CI/release reproduction | 4–7 days | Stable release candidate |
| 11 | Portfolio handoff | 2–4 days | Verified artifacts and measured results |

Likely total: roughly 54–93 focused engineering days for the full specification, not a weekend project.

## Appendix B — Resource assumptions and heavy-run policy

### Preliminary core budget (unmeasured target)

| Service group | Planned limit |
|---|---:|
| Neo4j Community (heap + page cache + overhead) | 1.5 GiB |
| Application PostgreSQL | 0.75 GiB |
| Lab PostgreSQL | 0.50 GiB |
| API + worker | 1.0 GiB |
| Three lab services + load generator | 1.0 GiB |
| Prometheus | 0.75 GiB |
| Redis | 0.15 GiB |
| Frontend/dev proxy and remaining core overhead | 0.60 GiB |
| **Aggregate core target** | **6.25 GiB** |

Configure Docker Desktop near 7–8 GiB, run one investigation and one bounded scenario at a time, cap Prometheus retention/log sizes, and measure actual resident memory in Phase 1/2. Optional Grafana/trace-backend profiles are off by default and must not push normal operation beyond the approximately 8 GiB target.

### What may need Colab

No Phase 0 command was heavy. The core project does not train a model and should not need a GPU.

- Local MiniLM embedding for 30–50 documents should be light enough on CPU; measure before moving it.
- Repeated Phase 9 evaluations are cost/time heavy because of hosted API calls, not GPU compute. They can run from a Colab replay notebook if desired, but the same frozen artifacts, lock metadata, secrets mechanism, and budgets must be preserved.
- Optional OpenRCA experiments are genuinely heavy (documented 32 GiB RAM/80 GiB storage recommendation) and should be Colab/high-memory or cloud-only extensions, never part of the core gate.
- Live Docker fault captures must still be demonstrated in the local Compose environment. Colab is not a reliable substitute for the required clone-and-run local workflow.

Before any command expected to take more than about 15 minutes, use substantial downloads, or exceed the local memory target, stop and provide the user with an exact Colab-compatible command/notebook path and expected artifacts.

## 6. How the user can try it

There is no runnable application in Phase 0. Review the saved plan and decisions with:

```bash
cd "/Users/mohammadrezakarami/Documents/New project/incidentgraph"
find docs -type f -maxdepth 3 -print | sort
sed -n '1,260p' docs/progress/phase-00-report.md
```

Expected behavior: the command lists one phase report, three continuity documents, and five ADRs. It starts no service, performs no network call, and changes no data. No cleanup is required.

## 7. Limitations and risks

| Risk | Likelihood / impact | Mitigation |
|---|---|---|
| Docker daemon unavailable | Current / high for Phase 1 | User starts Docker Desktop; run ARM64 image and health probes before coding beyond contracts |
| Parent directory is a mixed, uncommitted workspace | Current / high | Keep all work in `incidentgraph/`; initialize a standalone repo in Phase 1 only after approval |
| Python 3.12 and uv missing | Current / medium | Bootstrap pinned uv and managed Python 3.12 without changing system Python |
| Dependency churn across LangChain/LangGraph/provider packages | Medium / high | Joint resolution, exact lock, small API probes, wrapper interfaces, renovate only deliberately |
| Hosted model credentials/budget absent | Current / blocks Phase 5 real gate | Deterministic tests first; explicit provider and budget approval later |
| Neo4j Community authorization limits | High / medium | Separate ingestion/runtime adapters, reviewed templates, loopback network, least-privilege app boundary, document residual DB-credential risk |
| 16 GiB host contention | Medium / medium | 6.25 GiB core limits, optional profiles off, sequential captures, measure and tune |
| Evaluation leakage from labels/corpus | Medium / high | Separate build contexts/mounts, opaque IDs, cutoff checks, runtime path tests |
| Synthetic-case overclaiming | Medium / high | Preserve provenance category and group-level scoring; call it laboratory data |
| Corpus temporal inconsistency | Medium / medium | Version documents before final captures and enforce validity/cutoff filters |
| Large scope | High / high | Strict phase gates, reviewable vertical increments, no extensions before core gates |

## 8. What the user should understand

The central engineering distinction is between **job delivery** and **workflow state**. PostgreSQL leasing decides which worker may execute an investigation now. LangGraph checkpoints record where the investigation workflow can resume. Neither alone gives exactly-once behavior, so publication and review effects still require idempotency keys and fencing tokens.

Interview question 1: Why not use LangGraph checkpoints as the queue?

Answer: A checkpoint records graph state; it does not provide queue visibility, fair claiming, leases, heartbeats, retry scheduling, or stale-worker fencing. Those are scheduler responsibilities.

Interview question 2: Why use Neo4j as well as vector similarity?

Answer: Vector similarity finds semantically related text, while explicit, versioned service/resource relationships let retrieval include evidence about dependencies and preserve the provenance path. Graph reachability remains potential impact, not proof of observed impact or causality.

## 9. Next phase

Phase 1 will create the standalone repository foundation, pin Python 3.12/uv and Node/npm dependencies, pin container images by version/digest, implement typed configuration and initial domain contracts, start the core stores, add thin API/authentication, and prove a non-AI durable test job survives a controlled worker restart.

Required user decisions before paid or external work:

1. Approve starting Phase 1 in `/Users/mohammadrezakarami/Documents/New project/incidentgraph` and initializing it as a standalone Git repository.
2. No model-provider or monetary approval is needed for Phase 1. Provider selection and a small smoke budget can remain pending until Phase 5.
3. Start Docker Desktop before the Phase 1 container compatibility gate. If it is not running, Phase 1 can begin with contracts but cannot pass.

## 10. Resume state

- Current project path: `/Users/mohammadrezakarami/Documents/New project/incidentgraph`
- Git: the parent workspace is on `main` with no commits and many unrelated untracked files; `incidentgraph` is not yet an independent repository.
- Dirty state caused by this phase: only the nine English planning/ADR files listed in Section 2.
- Last verified command: Docker engine status check; failed because the daemon was not running.
- Outstanding commands: none.
- Exact next task after approval: initialize the standalone `incidentgraph` repository, add a focused `.gitignore`, install/pin uv and Python 3.12 for the project, then run a minimal dependency-resolution and import compatibility probe before creating application code.

Awaiting approval to begin Phase 1.
