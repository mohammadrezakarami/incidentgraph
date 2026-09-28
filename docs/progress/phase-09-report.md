# Phase 9 Progress Report — Frozen Evaluation and Error Analysis

Date: 2026-09-25

Status: **COMPLETE — QUALITY GATE FAIL**

Roadmap position: 10 of 12 gated phases are decided. Phases 0–8 passed, Phase 9 completed its
frozen evaluation but failed the agreed quality targets, and Phases 10–11 have not started.

## 1. Decision

The zero-paid-cost free-Colab run completed all 12 shards and all 120 planned agent jobs. The
20-question retrieval comparison also completed. Re-running finalization from the per-job records
reproduced `aggregate.json` and `per-case.csv` byte-for-byte:

- Returned archive SHA-256: `34b1413c93e92733381b52c1de4a03f28ede626d0e4d09e2fc358ab8ceafbc06`.
- Reproduced pre-review aggregate SHA-256: `cdf77609bf2712484d21947cadbc95f92f93eced3a64260d49313349e66ff342`.
- Reproduced per-case SHA-256: `bfcf14b5b105964c3b67b009ae11fb9c757aeedb22cbc01b408a95e72e137653`.

The Phase 9 gate is **FAIL**. The result is retained as measured; no prompt, model, dataset, seal,
scoring rule, or target was changed after held-out evaluation.

## 2. Frozen target results

| Target | Frozen threshold | Result | Status |
|---|---:|---:|---|
| Graph retrieval Recall@5 | >= 0.80 | 0.925 | PASS |
| Adaptive diagnosis Top 1 | >= 0.75 | 0/20 (0.000) | FAIL |
| Adaptive diagnosis Top 3 | >= 0.90 | 0/20 (0.000) | FAIL |
| Appropriate abstention | >= 4/5 | 5/5 | PASS |
| False incidents | <= 1/5 | 0/5 | PASS |
| Citation validity | 100% | 77/78 (98.72%) | FAIL |
| Policy violations | 0 | 3 blocked attempts | FAIL |
| Warm p95 active duration | < 90 s | 280.463 s | FAIL |
| Supported factual claims | >= 95% | 32/57 (56.1%) | FAIL |
| Core coverage | >= 85% | 49.45% retained result | FAIL |

Estimated monetary cost was USD 0. The policy violations were denied unauthorized-service attempts;
the run does not show unauthorized execution. The frozen scorer nevertheless counts the attempts,
so the target correctly remains failed.

## 3. Baseline comparison

| Workflow | Top 1 | Top 3 | Abstention | False incidents | Task completion | Citation validity | p95 active |
|---|---:|---:|---:|---:|---:|---:|---:|
| fixed | 0/20 | 0/20 | 0/5 | 0/5 | 0/30 | 0/0 | 1.423 s |
| adaptive | 0/20 | 0/20 | 5/5 | 0/5 | 28/30 | 77/78 | 280.463 s |

The fixed workflow failed before report generation in all 30 held-out cases because its roughly
22k–24k-token prompt exceeded the frozen model's 4,096-token context. Its short p95 therefore
reflects fast failure, not good performance. The adaptive workflow produced 30 inconclusive outcomes
and completed 28 tasks, but never returned an accepted component-and-mechanism diagnosis on the 20
identifiable cases.

The held-out retrieval comparison remained useful:

| Variant | Recall@5 | MRR@5 | nDCG@5 | Mean elapsed |
|---|---:|---:|---:|---:|
| vector | 0.8833 | 0.9500 | 0.9152 | 174.017 ms |
| hybrid | 0.9083 | 0.9250 | 0.9075 | 134.469 ms |
| graph | 0.9250 | 0.9250 | 0.9167 | 195.363 ms |

## 4. Written claim-support review

The generated 20-row template contained 10 fixed-workflow rows with `report: null`; those rows
cannot count as reviewed reports. They are retained in `manual-review.jsonl`, and adaptive held-out
cases 11–20 were added deterministically. The completed file therefore contains 30 rubric rows:
20 actual reports and 10 retained no-report baseline failures.

The rubric counts unique atomic externally verifiable claims in observed symptoms, observed or
potential impact, and hypothesis mechanism/explanation fields. Summary restatements are deduplicated;
recommendations, schema metadata, and explicit epistemic limitations are excluded. A claim passes
only when cited eligible run evidence directly entails it. In particular, topology adjacency is not
causality, a success series is not an error series, and qualitative elevation requires a cited
baseline or threshold.

Result: **32/57 supported atomic claims (56.1%), FAIL against 95%**.

This is a written, claim-by-claim Codex semantic review. It is explicitly AI-assisted and is not
represented as independent human validation. The exact counts, unsupported claims, reviewer label,
selection, and method are stored in `manual-review.jsonl` and `manual-review-summary.json`.

## 5. Representative failure analysis

1. **Fixed context overflow:** the fixed workflow assembled far more context than the 4,096-token
   model window, so it produced no reports and no meaningful baseline task completion.
2. **Tool-call schema mismatch:** adaptive runs repeatedly proposed invalid argument names or omitted
   required bounded-window fields. The policy layer rejected these calls safely, but useful evidence
   was lost.
3. **Authorization-name mismatch:** the model sometimes used aliases such as `checkout` or `payments`
   where canonical authorized IDs were required. These attempts were blocked and counted as policy
   violations.
4. **Timeout and model-capacity fallback:** multiple adaptive runs exhausted model-call budgets,
   timed out, or returned invalid structured output, producing deterministic partial reports.
5. **Metric semantics:** some reports described an `outcome=success` dependency series as an error
   rate. Citation IDs resolved, but the cited record did not support the claim, demonstrating why
   citation validity and factual support are separate targets.
6. **Unsupported causality:** several reports treated a dependency edge plus one metric series as a
   causal chain or user-facing impact. The evidence supported adjacency or observation, not cause.
7. **Temporal mismatch:** most runbooks were ineligible because the sealed incident captures predate
   the final corpus validity windows. This limitation was documented before the run and was not
   repaired after opening held-out results.

## 6. What passed

- Both held-out seals and all frozen-file hashes remained unchanged.
- Every planned job and retrieval row completed at zero estimated monetary cost.
- Per-case records reproduce the published automated aggregates exactly.
- Graph retrieval exceeded the frozen Recall@5 target.
- The adaptive workflow abstained on all five insufficient-evidence cases.
- Neither workflow asserted a false incident on the five healthy cases.
- Authorization and bounded-tool enforcement failed closed; no unauthorized execution occurred.

## 7. Next iteration proposal

Do not rewrite this frozen result. A new version should be separately sealed and should:

1. create post-corpus incident captures so eligible runbooks exist at each observation cutoff;
2. cap and summarize fixed-workflow context below the selected model's verified context window;
3. expose canonical tool schemas more effectively and validate model-generated calls before retry;
4. distinguish success, error, latency, and rate series in model-facing summaries;
5. reserve enough free-runtime budget for the model while enforcing a p95-compatible deadline; and
6. obtain an independent human audit of the claim rubric before making a human-validation claim.

Phase 10 is not started. Proceeding requires an explicit decision whether to accept this failed
quality gate as the portfolio result or authorize a separately versioned Phase 9 iteration.

## 8. Separately versioned corrective iteration (v2)

The user authorized a corrective Phase 9 iteration on 2026-09-25. The frozen v1 artifacts above
remain unchanged. The v2 implementation is currently **READY FOR FREE-COLAB REGRESSION**, not passed:

- model context is compact, non-duplicated, and capped at 12,000 characters; all 16 existing
  independent capture groups were checked locally and the largest constructed context was 7,778
  characters;
- trusted code now constructs canonical authorized service IDs, immutable timestamps, and strict
  tool arguments, so the local model selects bounded observation bundles rather than emitting raw
  tool calls;
- error-rate context includes only `outcome=error` series, while latency, pool, cache, and CPU units
  are stated explicitly;
- the diagnosis schema uses a documented finite ontology, and an uncitable proposed cause becomes
  an honest inconclusive report instead of an invalid citation;
- fixed and adaptive workflows share the same read-only tools and a maximum of 14 tool calls; the
  adaptive path remains a LangGraph workflow and uses at most three local-model calls;
- the monetary ceiling remains USD 0, and the 120-job workload is restricted to the free-Colab
  notebook `phase9_v2_colab.ipynb`.

The old held-out set is now marked consumed and may only be used as a development regression. Even
if every v2 regression check passes, the Phase 9 quality gate remains pending until a new post-corpus
capture set is created and sealed before opening its labels, followed by the required independent
human review of at least 20 reports. Whole-project non-integration coverage currently measures
47.40%, so the original 85% coverage target also remains an explicit failure rather than being
removed or redefined in v2.

### v2 returned result — 2026-09-28

The free-Colab corrective regression completed all 120 jobs and reproduced its aggregate and
per-case files byte-for-byte from the twelve shard records. The fixed workflow reached Top 1/Top 3
of 3/20, abstention of 0/5, four false incidents among five healthy cases, and task completion of
19/30. The adaptive workflow reached Top 1/Top 3 of 3/20, abstention of 0/5, two false incidents,
and task completion of 16/30. Citation validity, zero blocked unauthorized attempts, and warm p95
latency passed; the quality gate did not.

The dominant new failure was overly strict structured-output coherence validation: 49 reports were
discarded because a non-causal outcome was paired with a non-healthy mechanism, six plans paired
`finish` with a bundle value, and two non-causal reports retained a component. Two additional model
calls timed out. Among reports that passed schema validation, `cache_degradation` dominated the
predictions because raw nonzero cache misses were shown without a baseline, ratio, or abnormality
threshold. The returned artifacts and hashes are retained under
`artifacts/evaluation/phase9-v2-consumed-regression/`.
