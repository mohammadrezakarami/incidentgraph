# Final readiness report

Date: 2026-09-29

## Decision

**PORTFOLIO GATE: PASS.** All **12 of 12** gated phases (Phase 0 through Phase 11) are complete at
the defined local portfolio scope. IncidentGraph is ready for a repository walkthrough, a
five-minute replay/live demonstration, and truthful placement under Personal Projects.

**PRODUCTION READINESS: NOT CLAIMED.** This project is explicitly **not production-ready** and has
no public deployment, production credentials, enterprise identity, automatic remediation, or
real-organization outcome evidence.

## Phase 11 acceptance matrix

| Requirement | Evidence | Result |
|---|---|---|
| Final technical report | `docs/portfolio/FINAL_TECHNICAL_REPORT.md` | PASS |
| Approximately five-minute repeatable demo | `docs/portfolio/DEMO_SCRIPT.md`; `make portfolio-screenshots` | PASS |
| Architecture and agent-state diagrams | `docs/portfolio/DIAGRAMS.md` | PASS |
| Sanitized screenshots | Three PNGs plus provenance note under `artifacts/portfolio/` | PASS |
| Benchmark tables and failure history | Final report, frozen v1/v3/v4 artifacts | PASS |
| Explicit limitations | Final report, claims map, this readiness report | PASS |
| Three to five CV bullets | Five bullets in `docs/portfolio/CLAIMS_EVIDENCE.md` | PASS |
| Every CV claim maps to code, tests, data, and result evidence | Executable `tests/unit/test_portfolio.py` plus manual path review | PASS |
| Concise technical defense | Twelve answers in `docs/portfolio/TECHNICAL_DEFENSE.md` | PASS |
| No paid or heavy local model run | Screenshot/demo path made zero model calls; frozen evaluation was only replay-verified | PASS |

## What is actually demonstrated

- A working three-service transaction laboratory with bounded faults, metrics, logs, traces, and
  immutable captures.
- A versioned Neo4j service graph and 37-document provenance-aware corpus with incremental
  ingestion, vector/full-text indexes, and time-valid graph expansion.
- A typed 12-node LangGraph investigator using LangChain model/tool boundaries and eight read-only
  tools under deterministic authorization and resource limits.
- PostgreSQL-backed queueing, fencing, checkpoint recovery, review interrupt/resume, cooperative
  cancellation, and immutable follow-up report versions.
- An authenticated FastAPI/React console with resumable SSE and API-backed evidence drill-down.
- Frozen evaluation that preserves historical failures and a separately sealed v4 laboratory pass.
- A clean-clone local release path, offline regression suite, backup/restore, and safe shutdown.

## Evidence that must stay attached to claims

- Retrieval: 20 sealed project-authored questions; graph Recall@5 0.925; 37-chunk corpus.
- V4 agent: 30 variants over 11 capture groups; 20 identifiable cases; both workflows 20/20
  Top-1/Top-3; adaptive 5/5 abstentions and 0/5 false incidents; paid cost estimate USD 0.
- Claim review: 69/69 atomic claims across 20 reports, representing seven capture groups;
  **AI-assisted**, not independent human validation.
- Coverage: 85.14% branch-aware combined coverage for the explicitly frozen core scope, not the
  whole repository.
- Browser screenshots: deterministic zero-model fixture proving real UI/API/PostgreSQL wiring, not
  diagnosis quality.
- Local resource snapshot: one lightweight point-in-time observation, not a capacity or SLO study.

## Remaining work outside the completed portfolio scope

1. **Remote verification.** Inspect CI, security, full image build, and Trivy results after each
   published revision; remote workflow status is not part of the committed local evidence.
2. **Independent review.** Replace or supplement the AI-assisted rubric with independent domain
   reviewers and a larger, organization-independent dataset.
3. **Real-environment adaptation.** Add enterprise identity, centrally managed read-only telemetry
   credentials, data-governance review, retention policy, and representative service mappings.
4. **Operational validation.** Run sustained load, failover, queue saturation, trace-export outage,
   restore drills, and multi-worker tests on target hardware.
5. **Provider governance.** Approve a model/provider, residency and privacy terms, cost controls,
   and model-regression policy before any organization-facing use.
6. **Public deployment, if desired.** No public endpoint exists. Deployment would require a new
   security and operations gate; it is not necessary for the local portfolio claim.

No public deployment has been performed.

## Presentation safeguards

- Say “personal project” and “controlled laboratory,” not “production platform.”
- Say “supported by the cited laboratory evidence,” not “proved root cause.”
- Explain that v4's trusted policy owns the synthetic diagnosis while the model orders bounded
  observations.
- Mention v1 and v3 failures; they demonstrate honest evaluation and motivate the narrower v4
  design.
- Never expose `.env`, bearer tokens, database DSNs, Docker environment output, or evaluator labels.
- Do not imply that accepting a report executes a recommendation.

## Final position

The portfolio gate is closed with reproducible evidence and explicit limitations. The project may
be described as complete **for its defined local portfolio scope**. It must not be described as a
production-ready, enterprise, autonomous-remediation, or independently validated system.
