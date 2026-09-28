# Phase 9 repair in progress — 2026-09-28

Phase 9 evaluation execution completed, but the user's requested quality repair is still open.
Do not equate a completed FAIL report with a working diagnostic agent or proceed to Phase 10.

## Reproduced defects

1. On the saved first-repeat development adaptive traces, downstream latency, pool exhaustion,
   dependency errors, cache degradation and CPU contention were present in the derived signals,
   but the reports said `no_incident_detected`. The v3 normalizer never rejected that combination.
2. Adaptive traces stopped after the resource bundle and omitted `get_recent_changes`. The
   deployment case therefore had no deployment signal; the ambiguous change-plus-latency case
   appeared to have only a latency candidate. Changes existed in the matching fixed traces.
3. Model-facing observations contained valid UUIDs, but reports cited none. This is not archive
   corruption. The cause of the model's failure to use those identifiers cannot be proven without
   its raw diagnosis output; v3 did not retain that response. Verbose prompts and detached
   signal-to-source mapping are plausible contributors, now directly testable.
4. The v2 report renderer reused by v3 emitted empty observation lists for healthy/inconclusive
   outcomes. Even valid available citations disappeared from those reports.

## Implemented development repair

`src/incidentgraph/phase9_repair.py` is separate from the frozen v1/v2/v3 files.

- A bounded LangGraph collection workflow requires both resource and change observations. The
  model can choose order but cannot stop before completeness. This sacrifices early-stop savings;
  no adaptive efficiency advantage is claimed.
- Numeric facts retain service, labels, units and exact evidence identity. Model-facing references
  are short `F1`-style aliases. Trusted code maps selected aliases back to the original UUIDs.
- The existing lab thresholds are retained. Derived candidate mechanisms link to their underlying
  facts. No evaluator answer or scenario label is added to the model input.
- Validators reject unknown/duplicate citations, an unsupported mechanism/component, a healthy
  conclusion despite abnormal signals, and causal/healthy conclusions with missing or competing
  observations. A bad response is not silently counted as a successful healthy report.
- Successful-report observations retain citable numeric facts for all outcome types. Inconclusive
  summaries describe the model's failure to establish a cause rather than asserting the dataset
  itself is unanswerable.
- Missing finite percentiles are distinguished from zero. A successful-request percentile may
  be absent when requests fail; that does not erase independent pool-saturation evidence.
- The free-Colab diagnostic probe uses ten pre-existing development capture groups only, with at
  most two diagnosis attempts per group. It persists raw responses, validation errors, prompts,
  source hashes and per-case checkpoints. Explicit 8192-token context is sent per model request.

## What is verified and what remains

Eighteen targeted deterministic tests pass, including all six fault families, healthy, physically
missing telemetry, ambiguity, wrong citations, bounded retries, offline network isolation and
premature adaptive finish. Development prompts shrink from roughly 8.5–10.3k characters to under
3k. These are contract tests with saved observations, not real-model quality results.

The complete lightweight suite passes 101 tests; Ruff and strict mypy pass. Whole-project branch
coverage is 50.31%, still below 85%. The new repair module itself has 88% coverage; that is not a
replacement for the whole-project gate and the failing threshold was not lowered.

The next artifact is `phase9_repair_colab.ipynb` with `incidentgraph-phase9-repair.bundle`.
It does not need Neo4j, Docker, new captures or the old progress ZIP. Its output is
`phase9-repair-probe.zip`. Even a successful 10-case diagnostic replay cannot replace a full
workflow test or a fresh, sealed held-out evaluation. Do not automatically launch another 120 jobs.

Still open: real-model validation, integration of the validated repair into the next evaluation
and product path, whole-project coverage >=85%, and the required human claim-support rubric.
The previous written AI review is not independent human validation. The v3 held-out set has now
been opened and must not be presented as a fresh holdout after tuning. Current v3 scores and
frozen files remain historical evidence; no quality PASS is claimed by this repair.
