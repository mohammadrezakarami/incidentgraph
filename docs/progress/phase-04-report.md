# PHASE 4 REPORT — Retrieval Baselines and Development Evaluation

Status: PASS

Date: 2026-09-23

Roadmap position: Phase 4 of 11 delivery phases is complete. Counting discovery Phase 0, 5 of 12 gated phases are complete and 7 remain.

## 1. Objective and result

Phase 4 was intended to put vector-only, hybrid, and graph-enhanced hybrid retrieval behind one safe interface and compare them on the same versioned corpus before building an investigator. It now provides bounded Neo4j retrieval, reciprocal-rank fusion, authorization and as-of filtering, exact graph-path provenance, typed evidence, a pre-sealed 20/20 development/held-out fixture, and executable Recall@5, MRR@5, and graded nDCG@5 evaluation.

The phase passes. On the 20-question development split, graph-enhanced retrieval scored Recall@5 0.908, MRR@5 1.000, and nDCG@5 0.957. The held-out split was seal-verified and not evaluated. No hosted model, paid API, GPU, external dataset, or Colab run was needed.

## 2. Implemented changes

- `src/incidentgraph/retrieval.py` contains the shared request/result models, local query embedding, vector and sanitized full-text search, reciprocal-rank fusion, graph expansion, context selection, evidence conversion, evaluation metrics, seal verification, artifacts, and CLI.
- `EvidenceItem` now carries optional evidence windows, validity, snapshot, reviewed query-template ID, safe parameters, content, unit, and aggregation fields while preserving earlier contracts.
- `data/evaluation/retrieval-questions-v1.jsonl` contains 40 questions: 20 development and 20 held-out, with explicit split, group, service, environment, cutoff, and authorization scope.
- `data/evaluator/retrieval-labels-v1.jsonl` remains outside agent/runtime data and contains graded source relevance.
- `data/evaluator/retrieval-heldout-seal-v1.json` records the pre-tuning SHA-256 digest `a77524916562fdd4337e88d0efa295813fe05e0910d1a2bc1c51f9ff2d778c3c`.
- `tests/unit/test_retrieval.py` covers query sanitization, hard limits, rank fusion, context budgets, metrics, and tamper detection.
- `tests/integration/test_phase4_retrieval.py` exercises the real local model and Neo4j indexes, alias resolution, temporal/trust filtering, authorization rejection, shared contracts, and the required graph-only case.
- `artifacts/evaluation/phase4-dev/` retains machine-readable results, per-question CSV, and a concise Markdown comparison.

The project remains compact: retrieval and its evaluator are one module rather than a new hierarchy of small packages.

## 3. Retrieval contract and safety

All variants use corpus `incidentgraph-lab-corpus-v1-466b7569b585`, MiniLM revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, environment `lab`, and cutoff `2026-09-23T12:00:00Z` for this comparison.

| Bound | Value |
|---|---:|
| Vector candidates | 20 |
| Full-text candidates | 20 |
| RRF constant | 60 |
| Graph depth | at most 2 |
| Graph nodes | at most 50 |
| Allowed graph relationship | `DEPENDS_ON` |
| Final chunks | at most 8 |
| Final tokens | at most 5,000 |

The target service is resolved from reviewed IDs, names, or aliases and must be in the caller's authorization scope before search. Graph neighbors are independently authorization-filtered. Candidate documents must match the corpus, environment-connected service scope, trusted/reviewed/reference status, and cutoff validity; archived, expired, outdated, and untrusted content is excluded.

Untrusted full-text input is reduced to a maximum of 32 alphanumeric/underscore terms and passed as a parameter. Candidate and traversal limits are validated before their bounded integer values appear in static query templates. Vector and Lucene scores are never added because they are not calibrated; hybrid ranking uses only reciprocal ranks.

Every selected item includes a stable UUID, source/version, service IDs, environment, observation/collection/validity times, content hash, freshness, limitations, corpus snapshot, reviewed query-template ID, safe parameters, content, and a Neo4j provenance reference. Graph-introduced items additionally retain every node and directed relationship with source and topology version.

## 4. Development comparison

| Variant | Recall@5 | MRR@5 | nDCG@5 | Mean local ms |
|---|---:|---:|---:|---:|
| Vector | 0.900 | 0.950 | 0.923 | 13.3 |
| Hybrid | 0.883 | 0.950 | 0.921 | 12.3 |
| Graph-enhanced hybrid | 0.908 | 1.000 | 0.957 | 15.7 |

These are development measurements, not held-out claims. Timing is a warm local Apple M4 measurement across one small corpus and includes per-question embedding and Neo4j retrieval; it is not a capacity benchmark.

The required counterexample is `rq-dev-004`: "Gateway latency rose while cache hits fell." The direct vector and hybrid variants scope retrieval to gateway documents and do not place either payment-cache source in the top five. Graph-enhanced retrieval reaches both `runbook-cache` and `doc-payments-cache-contract` through this exact path:

```text
svc-gateway
  -[DEPENDS_ON; declared-compose-topology-v1; incidentgraph-lab-topology-v1]->
svc-checkout
  -[DEPENDS_ON; declared-compose-topology-v1; incidentgraph-lab-topology-v1]->
svc-payments
```

The path and both relationship provenance records are stored in `results.json`, not reconstructed for this report.

## 5. Evaluation integrity

The fixture has 40 question IDs and 40 matching label IDs. The 20 development and 20 held-out group sets are disjoint. Labels live under `data/evaluator/`, which is excluded from the Docker build context and not mounted into runtime services.

The held-out question lines and matching evaluator-label lines were sealed before retrieval tuning. Every verification and development run recomputes the digest and refuses a mismatch. Phase 4 evaluated only development IDs; the artifact explicitly records `evaluated: false` for held-out. Frozen evaluation remains a later gate.

## 6. Verification evidence

| Command | Result |
|---|---|
| `make verify-retrieval` | PASS — 20 dev, 20 held-out, disjoint groups, seal exact |
| `make lint` | PASS — Ruff reported no issues |
| `make typecheck` | PASS — strict mypy reported no issues in 16 source files |
| `make test` | PASS — 28 unit tests; 6 integration tests intentionally deselected |
| `make test-integration` | PASS — 1 PostgreSQL durability test; retrieval tests skipped by their separate gate |
| `make test-lab-integration` | PASS — 2 live lab tests |
| `make test-graph-integration` | PASS — 1 real Neo4j ingestion/resume test |
| `make test-retrieval-integration` | PASS — 2 real Neo4j/local-model retrieval tests |
| `make verify-captures` | PASS — all 17 Phase 2 capture contracts still pass |
| `make verify-ingestion` | PASS — graph, temporal, trust, index, source, and embedding checks pass |
| `make evaluate-retrieval-dev` | PASS — 60 runs, 20 questions × 3 variants; held-out not run |
| `make coverage` | FAIL / retained later-core gate — 41.02 percent versus 85 percent |

The implementation revision recorded in the evaluation artifact is `95d2de16ec5b93b088710042120c5c463e946de5`.

## 7. Acceptance checklist

| Criterion | Result |
|---|---|
| One interface for three retrieval variants | PASS |
| Approximately 20 vector and 20 lexical candidates | PASS — exactly 20 maxima |
| Hybrid uses RRF without raw-score mixing | PASS |
| Graph depth, node, relation, cycle, time, environment, and authorization controls | PASS |
| At most 8 chunks and 5,000 final tokens | PASS — observed maximum 793 tokens |
| Exact source and graph-path provenance | PASS |
| Typed evidence contract | PASS |
| 40 grouped questions with 20/20 split | PASS |
| Held-out sealed before tuning and not evaluated | PASS |
| Recall@5, MRR@5, and nDCG@5 executable | PASS |
| Direct baseline miss recovered by graph traversal | PASS |
| Same snapshot/cutoff/budgets across variants | PASS |

## 8. How I can try it

With Docker Desktop running and the existing `.env` at the repository root:

```bash
make verify-retrieval
make retrieve \
  VARIANT=graph \
  SERVICE=gateway \
  QUERY="Gateway latency rose while cache hits fell. Which downstream service should be investigated?"
make test-retrieval-integration
make evaluate-retrieval-dev
```

Results are written to `artifacts/evaluation/phase4-dev/`. These commands use the local CPU embedding model and small Neo4j corpus. Colab is unnecessary.

## 9. Limitations and risks

- The corpus, questions, and relevance judgments are project-authored laboratory material.
- Development labels influenced implementation validation, so their scores cannot estimate generalization.
- Hybrid is slightly below vector on this split. The result is retained honestly; held-out was not used to tune weights or query text.
- A 37-chunk corpus does not measure large-index latency, concurrency, or recall degradation.
- Topology expansion expresses operational relatedness, not incident causality.
- The global 85 percent later-core coverage target remains open at 41.02 percent.
- Phase 2 captures still predate the Phase 3 corpus and require recapture before final as-of evaluation pairing.
- No LLM reasoning, claim verification, report generation, or review workflow exists yet.

## 10. What I should understand

Vector retrieval answers "which text is semantically similar?" Full-text retrieval catches exact operational terms. Reciprocal-rank fusion combines their ordering without pretending their scores share a scale. Graph expansion changes the eligible service neighborhood using reviewed, time-valid topology and records exactly why a downstream document entered the result.

**Interview question: Why did graph retrieval help the cache case?** Direct retrieval was intentionally scoped to the target gateway service, so payment-only cache documentation was ineligible. The reviewed two-hop dependency path expanded eligibility to payments, then hybrid ranking surfaced the cache runbook and contract with the path attached.

**Interview question: Why seal held-out before tuning?** Without a precommitted digest, questions or judgments can drift after developers see results, turning the test set into another development set. The seal makes any later mutation detectable, while evaluator-only storage prevents the future investigator from reading answers.

## 11. Next phase

Phase 5 will build the single adaptive investigator and evidence-grounded incident report. It introduces model use, so it requires explicit user approval plus a provider/model and monetary/call budget decision. No Phase 5 work or paid call begins automatically.

## 12. Resume state

- Branch: `main`.
- Phase 4 implementation commit: `95d2de1`.
- Docker: all eight services were healthy at final verification.
- Corpus: `incidentgraph-lab-corpus-v1-466b7569b585`.
- Retrieval artifact: `artifacts/evaluation/phase4-dev/results.json`.
- Held-out: sealed, verified, not evaluated.
- Exact next action: wait for explicit Phase 5 approval and provider/model/cost-budget direction.

Awaiting approval to begin Phase 5.
