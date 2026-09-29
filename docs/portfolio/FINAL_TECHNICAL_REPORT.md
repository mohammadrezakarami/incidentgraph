# IncidentGraph final technical report

Date: 2026-09-29

Release scope: local, containerized, read-only portfolio system

Roadmap result: Phases 0–11 implemented and verified at their documented gates

## Executive summary

IncidentGraph is an evidence-grounded infrastructure-incident investigation system for a controlled
three-service laboratory. It combines real service telemetry, immutable replay captures, a
versioned Neo4j operational graph and document corpus, an adaptive LangGraph investigator,
LangChain structured model/tool boundaries, durable PostgreSQL execution, and an authenticated
React console.

The intended user is an engineer learning from or investigating a bounded incident window—not an
autonomous remediation system. The investigator can read approved evidence, explain what it
observed, cite immutable records, abstain when evidence is insufficient, and pause for human
review. It cannot run shell commands, generate arbitrary PromQL or Cypher, access production, or
change infrastructure.

The defined portfolio scope is complete. The system is not production-ready: its data is
project-authored, its final quality study is small, its semantic review is AI-assisted, its local
identity controls are not enterprise IAM, and no public deployment or organizational outcome is
claimed.

## Problem and user journey

Infrastructure evidence is usually split among metrics, logs, changes, dependency context, and
runbooks. A fixed text-retrieval answer can miss the next observation that matters, while an
unbounded agent can overreach, leak scope, or produce unsupported certainty. IncidentGraph explores
the middle ground:

1. An authenticated user supplies a service, time window, question, and LIVE or REPLAY mode.
2. The API stores an immutable run configuration and queues fenced work in PostgreSQL.
3. One investigator chooses among eight read-only tools through typed structured output.
4. Deterministic code enforces identity, service scope, time cutoff, query templates, novelty,
   budgets, and deadlines before a tool runs.
5. Evidence is validated, redacted, hashed, persisted, and referenced from checkpoint state.
6. The investigator updates hypotheses, gathers another useful observation, or stops at a hard
   limit.
7. A typed report must pass deterministic citation checks before durable human review.
8. Accept, reject, or request-revision decisions affect only the report lifecycle; no remediation
   action exists.

## Implemented architecture

The rendered system and state diagrams are in [`DIAGRAMS.md`](DIAGRAMS.md).

The interactive path is React → FastAPI → durable PostgreSQL work → worker/LangGraph. PostgreSQL
owns queue leases, events, checkpoints, evidence, reports, reviews, and report versions. Neo4j owns
versioned service relationships plus document vector and full-text indexes. Immutable captures
serve replay observations, and the live lab exposes bounded Prometheus and structured-log inputs.
The optional local model endpoint is loopback-only with a zero-dollar ceiling in verified runs.

The code remains deliberately compact: domain contracts are in `models.py`, orchestration in
`investigator.py`, registered evidence adapters in `investigation_tools.py`, GraphRAG in
`retrieval.py`, and durable storage in `persistence.py`/`durability.py`. The API, worker, and
frontend are separate deployable processes, while evaluation and capture tooling remain offline
workflows.

## Data origin and provenance

All incident and retrieval data is project-authored laboratory material.

- The transaction lab is `gateway → checkout → payments`, with PostgreSQL, Redis, Prometheus,
  structured logs, and propagated trace IDs.
- Six bounded fault families cover downstream latency, pool exhaustion, dependency errors, cache
  degradation, deployment regression, and resource contention. Healthy, ambiguous, misleading,
  and incomplete-evidence controls are also included.
- The curated corpus has 37 documents and 37 chunks with source hashes, versions, trust status,
  temporal validity, service scope, and licenses.
- Evaluator labels live under `data/evaluator/`, outside agent-readable captures and the runtime
  image context.
- Held-out manifests are sealed before evaluation. Previous failed v1 and v3 results remain
  immutable instead of being overwritten by v4.

An evidence item carries source/version, service IDs, environment, observation and collection
times, content hash, freshness, limitations, immutable snapshot/corpus references, a reviewed query
template ID, safe parameters, and exact graph-path provenance where relevant.

## Why the investigator is adaptive

The same question can require metrics, recent changes, logs, dependencies, or documents depending
on what the previous observation showed. The model therefore selects the next registered
observation using a short decision summary and typed tool request. It does not control the tool
implementation, identity, authorization, query text, or budgets. A fixed retrieval workflow is
retained as an evaluation baseline and is useful when the evidence plan is known in advance.

V4 deliberately narrows the model's role further: the local model controls bounded observation
order, while trusted pre-registered code applies the synthetic-lab diagnosis and citation policy.
That design repaired unreliable free-form conclusions, but it also limits how the final quality
numbers may be interpreted.

## Retrieval results

The three retrievers share the same corpus, cutoff, authorization scope, candidate limits, and
final context budget. Vector and full-text scores are not added; hybrid uses reciprocal-rank fusion.
Graph expansion follows only reviewed, time-valid `DEPENDS_ON` relationships to at most two hops
and 50 nodes.

### Sealed 20-question laboratory holdout

| Variant | Recall@5 | MRR@5 | nDCG@5 | Mean elapsed |
|---|---:|---:|---:|---:|
| Vector | 0.8833 | 0.9500 | 0.9152 | 174.017 ms |
| Hybrid | 0.9083 | 0.9250 | 0.9075 | 134.469 ms |
| Graph-enhanced | 0.9250 | 0.9250 | 0.9167 | 195.363 ms |

Graph achieved the best Recall@5, hybrid was fastest in this small run, and vector had the best
MRR@5. The result does not justify saying one approach dominates universally. A development
counterexample proves the architectural value: target-service-only vector/hybrid retrieval missed
payment-cache evidence, while graph expansion admitted it through the exact reviewed
`gateway → checkout → payments` path.

## Agent evaluation and repair history

The evaluation history is part of the product evidence rather than a hidden development story.

| Version | Freshness and outcome | Key result |
|---|---|---|
| v1 | Frozen historical holdout — FAIL | Adaptive Top-1/Top-3 0/20; 32/57 supported claims; 280.463 s warm p95; fixed workflow exceeded the 4,096-token context and produced no reports. |
| v2 | Consumed-data regression — not a held-out claim | Repaired context and tool-argument handling but remained unsuitable as final evidence because v1 answers had been opened. |
| v3 | Fresh post-corpus holdout — FAIL | Adaptive Top-1/Top-3 0/20; 3/5 abstentions; 0/20 supported factual conclusions. |
| v4 | Fresh post-repair holdout — PASS | All frozen targets passed under the narrower trusted synthetic-lab policy. |

### Final v4 frozen gate

| Metric | Fixed | Adaptive | Target result |
|---|---:|---:|---|
| Top-1 diagnosis | 20/20 | 20/20 | PASS |
| Top-3 diagnosis | 20/20 | 20/20 | PASS |
| Appropriate abstention | 5/5 | 5/5 | PASS |
| False incidents | 0/5 | 0/5 | PASS |
| Task completion | 30/30 | 30/30 | PASS |
| Citation validity | 106/106 | 106/106 | PASS |
| Policy violations | 0 | 0 | PASS |
| Warm p95 active duration | 0.018 s | 1.819 s | PASS (< 90 s) |
| Estimated paid cost | USD 0 | USD 0 | PASS |

The v4 run completed 120/120 jobs across fixed/adaptive held-out runs and three development repeats.
The 30 held-out variants share 11 captures and therefore are not 30 independent incidents. The
written AI-assisted rubric checked all 20 identifiable adaptive reports across seven represented
capture groups and found 69/69 supported atomic claims. It is not independent human validation.

The retained branch-aware core scope measured 85.14% combined coverage (1,868 covered lines, 373
covered branches, and 2,138 statements in the configured core modules). That is a scoped core
coverage result, not whole-repository coverage.

## Durability, security, and observability

- Queue work is at-least-once. Lease owner/token/expiry/generation and report-version fencing keep
  stale workers from publishing; externally visible effects use stable idempotency keys.
- Human-review waiting releases worker capacity. Decisions are role-checked, version-bound,
  expiring, idempotent, and stored before resume work is queued.
- Cancellation is cooperative and blocks later completion once observed; it cannot undo provider
  work already accepted.
- Follow-ups reuse the checkpoint thread, retain cumulative usage, receive an explicit incremental
  budget, and publish a new immutable report version.
- Prompt injection is constrained outside the prompt through typed schemas, a fixed registry,
  server-owned identity/scope, reviewed queries, immutable cutoffs, and hard budgets.
- API, worker, model, and tool spans share persisted W3C context. Prompts, raw evidence, model
  output, authorization, and DSNs are excluded from attributes; recursive redaction runs before
  local export.
- Local bearer identity, an in-process rate limiter, and loopback origin are development controls,
  not a public multi-tenant security design.

## Local resource and release evidence

The Phase 8 point-in-time profile—not a capacity benchmark—recorded 25/25 successful loopback
health requests with 0.397 ms median and 0.584 ms p95. Eight IncidentGraph containers consumed
about 1.27 GiB at capture time; Neo4j was still active and represented most of that snapshot.

The Phase 10 isolated clean clone installed locked runtimes and dependencies, then passed 150
offline backend tests, three frontend tests, a production frontend build, eight enabled service
integration tests, one real-API Playwright flow, frozen-v4 verification, PostgreSQL backup/restore
with post-restore smoke, and safe teardown. Normal teardown preserves named volumes. The optional
model profile is off by default.

## Reproduction paths

After cloning and installing Docker Desktop, Node 24.13.1, and npm 11.8.0:

```bash
./bootstrap.sh
.venv/bin/python scripts/create_local_env.py
make doctor
make up
make migrate
make demo
make test-offline
make evaluate-test
make report
make portfolio-screenshots
make portfolio-verify
```

`make demo` is deterministic and makes zero model calls. `make evaluate-test` verifies the committed
frozen v4 evidence; it does not rerun the 120-job model workload. Heavy model evaluation remains an
explicitly approved hosted-GPU procedure documented by the two retained versioned notebooks.

## Limitations and truthful positioning

- The corpus, incident captures, questions, and labels are small and project-authored.
- V4's variants share captures; its reports and claim-review rows are not all independent.
- The AI-assisted semantic review is not independent human evaluation.
- Trusted v4 policy code, not free-form model reasoning, owns the final synthetic-lab diagnosis.
- Retrieval and final-agent comparisons are separate experiments; v4 document retrieval is equally
  unavailable to both agent workflows.
- Correlation, graph adjacency, and temporal proximity do not prove causality.
- The UI screenshots use a deterministic zero-model fixture to prove the product path, not AI
  diagnosis quality.
- Remote GitHub workflow status is not part of the committed local verification evidence.
- The full backend image build and Trivy image scan are assigned to remote CI to avoid an
  unnecessary heavy laptop workload.
- There is no public endpoint, production credential, automatic remediation, enterprise IAM,
  external trace backend, sustained load study, or real-company MTTR result.

## Portfolio conclusion

IncidentGraph supports a truthful personal-project claim: it demonstrates design and implementation
of a bounded agentic system, operational GraphRAG, durable execution, evidence-based reporting,
measured failure analysis, and a reproducible local release. It does not establish prior employment
or production impact. The exact permissible CV statements and their evidence are in
[`CLAIMS_EVIDENCE.md`](CLAIMS_EVIDENCE.md).
