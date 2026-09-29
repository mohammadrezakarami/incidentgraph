# Five-minute IncidentGraph demo script

This demo is repeatable without a paid service, GPU, or local LLM. The browser path uses a clearly
labeled deterministic publisher so it can exercise the real FastAPI/PostgreSQL lifecycle quickly.
Diagnosis-quality claims come from the separate frozen v4 artifacts, not from the demo fixture.

## One-time setup

```bash
./bootstrap.sh
.venv/bin/python scripts/create_local_env.py
make doctor
```

Do not show the generated bearer token, `.env`, terminal history containing secrets, Docker
environment output, or database DSNs during a presentation.

## Pre-demo check

Run this before the call, not during the five-minute narration:

```bash
make portfolio-screenshots
make portfolio-verify
make evaluate-test
```

Expected result: one Playwright flow passes, three sanitized screenshots exist, portfolio checks
pass, and the frozen v4 verification reports 120 jobs, 9/9 targets, 20 reviewed reports, 69/69
supported claims, and estimated paid cost USD 0.

If Docker or the browser is unreliable during the presentation, use the committed screenshots in
`artifacts/portfolio/`; they were produced by the same tested flow.

## Timed narration

### 0:00–0:40 — Problem and boundary

Say:

> IncidentGraph is a local, read-only infrastructure incident investigator. It combines bounded
> telemetry, a versioned service graph and corpus, one adaptive investigator, durable human review,
> and evidence-linked reports. It never gets a remediation tool, arbitrary query execution, or
> production credentials.

Show the opening of `README.md` and the architecture diagram in
`docs/portfolio/DIAGRAMS.md`.

### 0:40–1:25 — Architecture

Point to the runtime diagram and explain:

- React talks only to authenticated FastAPI.
- PostgreSQL owns queue leases, checkpoints, events, reviews, evidence, and report versions.
- Neo4j owns time-valid dependencies and document vector/full-text indexes.
- The model chooses only the next registered observation; deterministic code owns authorization,
  query templates, budgets, citations, and v4's synthetic-lab diagnosis policy.

Then show the investigator state diagram. Mention the bounded observation loop, one report-repair
loop, and durable human-review interrupt.

### 1:25–2:35 — Product flow

Open `artifacts/portfolio/01-report-and-review.png`.

Explain that the image comes from a real browser → API → PostgreSQL flow. Identify:

- REPLAY mode and lifecycle status;
- persisted event and tool outcome;
- dependency graph;
- evidence-grounded report;
- explicit warning that review acceptance publishes a report but executes nothing.

Open `artifacts/portfolio/02-evidence-drilldown.png`. Point out source ID, fixture provenance,
immutable window, limitation, safe parameters, and the cited metric chart. State plainly that this
fixture makes zero model calls and proves product wiring—not AI diagnosis quality.

Open `artifacts/portfolio/03-completed-and-follow-up.png`. Explain immutable report versions and
that a follow-up gets a separate incremental budget.

### 2:35–3:25 — GraphRAG result

Open the retrieval table in `docs/portfolio/FINAL_TECHNICAL_REPORT.md`.

Say:

> On the sealed 20-question laboratory holdout, graph retrieval had the best Recall@5 at 0.925,
> hybrid was fastest, and vector had the best MRR@5. I do not claim universal superiority. The
> concrete value is a gateway question where service-scoped baselines missed payment-cache evidence
> and graph expansion admitted it through the reviewed two-hop dependency path.

Mention the 37-document corpus and that adjacency is not causality.

### 3:25–4:20 — Evaluation failures and repair

Open the v1/v3/v4 history table. Say:

> I retained failed evaluations instead of rewriting them. V1 failed because the fixed prompt
> exceeded context and the adaptive workflow produced unsupported conclusions. A fresh v3 run also
> failed. V4 narrowed the model to bounded observation ordering and moved the synthetic-lab
> diagnosis and citations into trusted pre-registered code. On a new sealed set it passed all
> frozen targets.

Then state the scope of the final result: 30 case variants, 11 capture groups, 120 jobs, USD 0,
20/20 Top-1 and Top-3, 5/5 abstentions, 0/5 false incidents, 106/106 valid citations, and an
AI-assisted 69/69 claim review. Explicitly say the variants are not all independent and the review
is not independent human validation.

### 4:20–5:00 — Durability, security, and close

Say:

> Queue delivery is at-least-once, while leases, generations, fencing, and idempotency protect
> externally visible effects. Prompt-injection defense lives outside the prompt: fixed tools, typed
> inputs, server-owned scope, reviewed queries, immutable cutoffs, and hard budgets. The clean-clone
> gate reproduced offline tests, the real browser flow, backup/restore, and safe teardown.

Close with:

> This is a completed local portfolio system, not a production deployment. The next real-world step
> would be enterprise identity, an approved telemetry adapter, an independently reviewed dataset,
> sustained load and failure testing, and a staged read-only pilot before any remediation discussion.

## Live command fallback

If the interviewer asks to see executable proof, run one of these short, zero-model commands:

```bash
make portfolio-verify
make evaluate-test
```

Do not start the free-Colab 120-job evaluation live. Do not enable a paid provider. Do not run a
full image rebuild on a resource-constrained laptop during the presentation.

## Expected questions

The concise answers for adaptive versus fixed retrieval, LangChain versus LangGraph, graph versus
vector similarity, durability, human review, prompt injection, leakage, and production readiness
are in [`TECHNICAL_DEFENSE.md`](TECHNICAL_DEFENSE.md).
