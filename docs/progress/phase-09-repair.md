# Phase 9 repair in progress — 2026-09-28

## Returned first probe and repair-2

The first real-model probe returned 0/10 and 20 attempts. Archive SHA-256:
`3bba0f3683f6a9d3a4399f8217c10b6524811ab614734fecef7de47884eb4075`.
The actual responses are retained in `tests/fixtures/phase9-repair-responses.json`.
Ten attempts failed cross-field validation, nine exceeded the three-source citation limit,
and one has no recorded model response and an empty exception message. The last error cannot
be classified retrospectively. All 19 recorded responses chose inconclusive. Several recognized
the active fault in prose, but that is not a correct diagnosis and is not rescored as success.

Repair-2 fixes the demonstrated contract defects:

- The model chooses one `decision` enum, at most three `evidence_refs`, and a short `rationale`.
  Code expands that choice into coherent outcome/component/mechanism/limitation fields. It never
  upgrades an inconclusive model choice to a probable cause.
- The response schema and report both permit at most three evidence sources. Previously the
  schema allowed six fact references while a hidden validator required <=3 source IDs.
- CPU facts now name the service from the actual `job` label. Only abnormal payments CPU backs
  the payments CPU candidate; checkout and gateway CPU are not required support.
- Deployment support now includes the approved change and abnormal dependency error, excluding
  zero-error series. Candidate rules expose the existing deployment error threshold of 1.0 rps,
  distinct from the generic dependency-error threshold of 1.5 rps. Thresholds were not changed.
- Exceptions now retain their type even when their message is empty. The first request allows
  additional cold-load time. Summaries separate valid reports from correct diagnoses and count
  validation failures, instead of presenting every failure as only `correct: 0`.

Thirty-two repair tests pass, including archived-response regression checks and successful and
failing mocked transport paths. Mocked 10/10 is a plumbing check, not model performance.
Repair-2 still requires a real-model probe; the fresh evaluation, product integration, global
coverage target and human review remain open. Do not claim that Phase 9 quality is repaired yet.

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
