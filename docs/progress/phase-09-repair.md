# Phase 9 repair in progress — 2026-09-28

## V4 workflow frozen; final Colab run pending

Repair-3 is now integrated into `phase9_v4_evaluation.py` without changing frozen v1/v2/v3 code.
Both fixed and adaptive workflows collect the same complete 14-result observation surface. The
adaptive model gets one bounded call to choose bundle order; trusted code forces both bundles and
alone produces the diagnosis, factual prose, and citations. End-to-end capture-replay tests verify
identical policy outcomes and exact eligible citations for both workflows.

The retained core scope (domain models, auth/API policy, investigation tools, investigator,
retrieval, repair policy, and v4 workflow) now has 85.14% branch-aware combined coverage. Ruff,
strict mypy, and all 145 selected non-integration tests pass. Whole-repository coverage is still a
separate informational metric; evaluation/CLI/reporting tails were not counted as core runtime.

Eleven new post-repair live laboratory captures were produced with bounded six-second workloads,
one for every fault/control scenario. They form a fresh 30-case held-out set with 20 identifiable,
five healthy, and five insufficient cases. The 11 capture groups are independent; question
variants sharing a capture are explicitly not independent. The held-out seal digest is
`b36dc01092ddc22565f061a4401b6710b9e77a46e5a10f3efc4a78058f23435d` and freeze
`phase9-v4-fresh-post-repair` verifies 28 files/manifests.

The free-Colab handoff is `phase9_v4_colab.ipynb` plus
`incidentgraph-phase9-v4-colab.bundle` (SHA-256
`c31bb3a80b83ae2482eedd8364d3cfd2f3a9f60931dd10f263f2ee2bccb2c03f`). It needs no Docker or
Neo4j and makes at most 60 local-model planning calls across 120 jobs; fixed cases make zero model
calls. Phase 9 remains open until `phase9-v4-progress.zip` returns, its aggregates reproduce, and at
least 20 fresh reports receive the written support rubric. No v4 quality PASS is claimed yet.

## Returned repair-2 probe and repair-3 bounded policy

The returned repair-2 archive is preserved under
`artifacts/evaluation/phase9-repair2-probe/`. Its archive SHA-256 is
`6b82caa667b49351e6595291ccd36ebe8cc2bbe44b43ad78f06f540777dae86b`.
It produced 10 structurally valid reports in 11 model calls, but only 7/10 eventual label matches
and 6/10 first-pass matches. The pinned 4B model wrongly abstained on two complete payments
dependency-error cases and one complete healthy case. One ambiguous case required a retry.
Several accepted rationales also misdescribed zero or unrelated measurements, so structural
validity was not equivalent to factual support.

Repair-3 removes that unsafe free-form decision boundary. Trusted code now applies the already
pre-registered synthetic-lab thresholds and exact service/edge scoping:

- missing required telemetry or multiple active mechanisms yields `insufficient_observation`;
- one complete active mechanism yields that probable cause and its exact component;
- complete telemetry with no active mechanism yields `no_incident_detected`;
- checkout deployment regression requires an approved **checkout** change and a matching
  gateway-to-checkout error signal; an unrelated service change cannot trigger it;
- dependency errors require the checkout-to-payments edge, and latency, pool, cache and CPU facts
  remain scoped to their actual service.

Explanations and cited fact selections are generated from trusted templates. A derived policy
evidence item is cryptographically linked to the complete source trace and every raw fact evidence
ID, making completeness/healthy claims auditable without arbitrary three-fact sampling. Reports
carry the actual case target, zero replayed model/tool calls, the repair-3 policy version, source job
ID and source-trace digest. Frozen v1/v2/v3 implementations and artifacts remain unchanged.

The lightweight repair-3 development replay is preserved under
`artifacts/evaluation/phase9-repair3-development/`. It made no model, network, Docker or paid calls:

- 11/11 structurally valid reports;
- 11/11 deterministic evidence-support checks;
- 11/11 development label matches (7 identifiable, 2 insufficient/ambiguous, 2 healthy);
- 0 model calls and USD 0 cost.

The eleventh control is the previously omitted healthy-high-traffic case, reconstructed
deterministically from its immutable development capture. Thirty-eight targeted repair tests and
the complete 121-test non-integration suite pass. Ruff and
strict mypy pass using the already-installed project environment. This is a consumed development
replay, not a free-form model-accuracy claim, fresh holdout, human supported-claim review, or Phase
9 PASS. Integration into a newly frozen workflow, fresh independent evaluation, human review, and
the retained 85% coverage gate remain open.

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
At this point repair-2 still required a real-model probe. That probe has now returned and failed
the quality check as documented above; repair-2 is retained only as historical failure evidence.

The historical repair-2 deliverable `phase9_repair_colab.ipynb` required
`incidentgraph-phase9-repair2.bundle` and returns `phase9-repair2-probe.zip`. Its four cells reuse
an already running matching Ollama server where possible. Do not rerun or upload that obsolete
repair-2 bundle; repair-3 needs no model probe.

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

At the first-repair checkpoint, eighteen targeted deterministic tests passed, including all six fault families, healthy, physically
missing telemetry, ambiguity, wrong citations, bounded retries, offline network isolation and
premature adaptive finish. Development prompts shrink from roughly 8.5–10.3k characters to under
3k. These are contract tests with saved observations, not real-model quality results.

At that checkpoint the complete lightweight suite passed 101 tests; Ruff and strict mypy passed. Whole-project branch
coverage is 50.31%, still below 85%. The new repair module itself has 88% coverage; that is not a
replacement for the whole-project gate and the failing threshold was not lowered.

That checkpoint's next artifact was `phase9_repair_colab.ipynb` with
`incidentgraph-phase9-repair.bundle`. Its returned probes are now superseded by the repair-3
development artifact above. A successful development replay still cannot replace a full workflow
test or a fresh, sealed held-out evaluation. Do not automatically launch another 120 jobs.

Those checkpoint blockers are now resolved for integration, scoped core coverage, and fresh
sealing as described at the top of this report. Still open: execute the frozen v4 comparison and
complete its required claim-support rubric. The previous written AI review is not independent
human validation. The v3 held-out set remains consumed historical evidence and is not reused as
the v4 held-out claim. No v4 quality PASS is claimed before the returned run is reviewed.
