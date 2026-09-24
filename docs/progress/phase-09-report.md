# Phase 9 Progress Report — Frozen Evaluation and Error Analysis

Date: 2026-09-24

Status: **IN PROGRESS — FROZEN, HEAVY RUN PENDING**

Roadmap position: Phase 9 of 11 delivery phases has started. Including discovery Phase 0,
**9 of 12 gates are complete**; the Phase 9 gate is not yet passed.

## 1. Result so far

The evaluation implementation, run plan, prompts, settings, scoring rules, datasets, corpus,
dependency lock, and zero-paid-cost budget are now frozen in
`config/phase9-freeze-v1.json`. Both pre-existing held-out seals verify unchanged:

- Retrieval: `a77524916562fdd4337e88d0efa295813fe05e0910d1a2bc1c51f9ff2d778c3c`.
- Incident: `1dbac7ea0da7702ad13c387743c2c5c795e45f3d81c78d857a98095cf25d8b67`.

No held-out retrieval or real-model agent result has been run locally. The expensive work is
deliberately deferred to the resumable free-Colab notebook. No paid service is configured or
authorized.

## 2. Frozen comparison

- Retrieval: 20 held-out questions, one deterministic pass each through vector, hybrid, and
  graph-enhanced retrieval with the same indexed corpus, embedding revision, cutoff, authorization,
  candidate limits, and final context budget.
- Agent: documented fixed observation rules versus the adaptive LangGraph investigator. Both use
  the same immutable captures, read-only tool implementation, graph retriever, Qwen generator,
  authorization, and per-case ceilings.
- Variability: three runs of both workflows on the same frozen 10-case development subset.
- Held-out: one affordable run of both workflows over all 30 incident cases.
- Total: 120 resumable agent jobs plus 60 retrieval rows.

The fixed workflow always requests target error rate, target latency, captured dependencies,
target logs, approved changes, and graph-enhanced runbooks before using the same report generator.
Actual model calls, tool calls, tokens, duration, and zero monetary cost are recorded per case.

## 3. Implemented artifacts

- `src/incidentgraph/phase9_evaluation.py`: freeze verification, fixed and adaptive runners,
  resumable sharding, held-out retrieval comparison, deterministic scoring, aggregation, error
  sampling, manual-review template, CSV/JSON/Markdown output, and CLI.
- `tests/unit/test_phase9_evaluation.py`: run-plan cardinality, exact component/mechanism scoring,
  citation resolution, abstention, false-incident, and denominator tests.
- `config/phase9-freeze-v1.json`: exact hashes, seals, model digest, prompt hashes, corpus snapshot,
  budgets, targets, and the known pre-run temporal limitation.
- `phase9_colab.ipynb`: free T4 setup, ephemeral Neo4j, frozen corpus ingestion, exact Ollama/model
  identity check, 12 resumable shards of 10 jobs, progress-zip import/export, and finalization.
- `artifacts/evaluation/phase9-frozen-v1/README.md`: artifact contract and pending state.
- `make verify-phase9-freeze`, `make evaluate-test`, and `make report`: the local test target refuses
  to start the heavy model run and points to Colab.

## 4. Verification before freeze

The deterministic local checks passed before the final freeze:

```text
.venv/bin/ruff check .
.venv/bin/mypy
.venv/bin/pytest -m "not integration" -q
.venv/bin/python -m incidentgraph.phase9_evaluation verify-freeze
```

Observed result: Ruff pass, strict mypy pass over 24 modules, 65 unit tests pass with 18 integration
tests deselected, and all 13 frozen files plus both held-out seals match.

## 5. Honest blocker and limitation

The latest sealed incident cutoff is `2026-09-22T21:48:44.837164+00:00`, while most final corpus
records are valid from `2026-09-23T00:00:00Z`. Therefore most runbooks are correctly ineligible for
the incident cases. Rewriting the capture timestamps, corpus validity, labels, or seals after the
fact would create leakage and is prohibited. Both agent workflows retain equivalent access, but
this frozen comparison cannot establish the intended final telemetry-plus-corpus pairing.

This limitation is recorded before opening held-out results and will remain in the final report.
A future iteration may create and seal a new evaluation version from post-corpus captures, but it
cannot replace or silently repair this run.

## 6. Remaining Phase 9 work

1. Run all 12 free-Colab shards and return the final `phase9-progress.zip`.
2. Reproduce automated aggregates from the 120 per-case records.
3. Complete the written support rubric over at least 20 deterministically sampled held-out reports.
4. Investigate representative failures and publish every target as PASS, FAIL, or PENDING with its
   numerator, denominator, provenance category, and limitations.

Until these steps finish, Phase 9 remains in progress and Phase 10 must not be marked started.
