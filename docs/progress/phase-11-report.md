# Phase 11 completion report — Portfolio handoff and technical defense

Date: 2026-09-29

Status: **PASS**

Roadmap position: Phase 11 of 11 delivery phases is complete. Including discovery Phase 0,
**12 of 12 gated phases are complete**.

## 1. Objective and result

Phase 11 converted the implemented system and its frozen evidence into a truthful, repeatable
portfolio handoff. It adds a final technical report, timed five-minute demo, repository-native
architecture and state diagrams, three sanitized screenshots from the real browser/API/PostgreSQL
flow, benchmark and failure tables, a 12-question technical-defense guide, and five CV bullets with
explicit code, test, dataset, result, and limitation mappings.

The gate passes. The project is complete for the defined local portfolio scope. Production
readiness, public deployment, independent human validation, enterprise controls, and business
impact remain explicitly unclaimed.

## 2. Delivered artifacts

- `docs/portfolio/FINAL_TECHNICAL_REPORT.md` — problem, users, architecture, provenance,
  implementation, retrieval and agent tables, v1/v3/v4 failure history, durability, security,
  release evidence, reproduction, and limitations.
- `docs/portfolio/DEMO_SCRIPT.md` — an approximately five-minute narration, one-time setup,
  zero-model preflight, screenshot fallback, and presentation safety checklist.
- `docs/portfolio/DIAGRAMS.md` — Mermaid architecture and exact 12-node investigator state machine,
  derived from implemented code. Repository-native diagrams avoid another folder or hosted design
  dependency.
- `docs/portfolio/CLAIMS_EVIDENCE.md` — five paste-ready personal-project CV bullets, each mapped to
  code paths, exact test IDs, dataset scope, result artifacts, and caveats.
- `docs/portfolio/TECHNICAL_DEFENSE.md` — concise answers to all 12 required architecture,
  durability, security, evaluation, and production-readiness questions.
- `docs/portfolio/FINAL_READINESS.md` — portfolio PASS decision, acceptance matrix, demonstrated
  scope, claim qualifiers, remaining external work, and presentation safeguards.
- `artifacts/portfolio/` — three PNG screenshots and a provenance/sanitization note.
- `tests/unit/test_portfolio.py` and `make portfolio-verify` — executable checks for documents,
  diagrams, CV evidence sections, PNG validity/dimensions, and visible limitations.
- `make portfolio-screenshots` — repeatable real-API screenshot generation using only `app-db` and
  the deterministic zero-model browser fixture.

## 3. Screenshot evidence

The existing Playwright flow was extended with opt-in screenshot capture. Normal E2E runs do not
rewrite portfolio assets. When `INCIDENTGRAPH_PORTFOLIO_OUTPUT` is set, the test captures:

1. report, event timeline, dependency view, and human-review boundary;
2. the cited metric evidence dialog with chart, provenance, and fixture label;
3. completed lifecycle and immutable versioned follow-up UI.

The three files are 1280 pixels wide and between 1832 and 1853 pixels tall. Visual inspection
confirmed that no bearer token, DSN, database password, model key, or real personal identity is
visible. The UI shows only the fixed `phase7-e2e-owner` principal and fixture provenance. The
report itself says it is a deterministic Playwright fixture, not an AI benchmark.

## 4. Verification evidence

The Phase 11 work ran no LLM, embedding model, GPU job, external service, or paid call.

| Command | Observed result |
|---|---|
| `make portfolio-screenshots` with an isolated temporary env/project | PASS — one real FastAPI/PostgreSQL/Playwright flow in 4.3 s; three PNGs generated |
| `make portfolio-verify` | PASS — 5/5 portfolio checks |
| `make test-offline` | PASS — 155 Python tests; 18 integration tests deselected; 3 Vitest tests; production frontend build |
| `make lint` | PASS — Ruff |
| `make typecheck` | PASS — strict mypy over 32 source files; TypeScript/Vite production build |
| `make evaluate-test` | PASS — 28 frozen files, 12 parts, 120 records, 9/9 targets, 20 reviewed reports, 69/69 claims, USD 0 |
| `make report` | PASS — committed v4 aggregate reproduced from existing artifacts; no model call |

The screenshot run used a separate Compose project and temporary ignored environment. The user's
existing `.env` was not overwritten.

## 5. Gate assessment

| Gate criterion | Result |
|---|---|
| Every CV claim maps to implementation and verification evidence | PASS — 5/5 statements carry code, test, dataset/result, and scope sections |
| Demo is repeatable | PASS — one command regenerates the same real product flow and three images; scripted fallback is documented |
| Architecture and agent state are explainable | PASS — code-derived diagrams plus source anchors |
| Benchmarks distinguish targets, results, and limitations | PASS — sealed retrieval and v4 results are tabulated; v1/v3 failures retained |
| User receives concise technical defense | PASS — all 12 required questions answered |
| Remaining work stays visible | PASS — publication, independent review, real-environment controls, operations, provider governance, and deployment are listed |
| No unsupported completeness or production claim | PASS — portfolio scope is complete; production readiness is explicitly not claimed |

## 6. Cost and resource boundary

- Model calls: 0.
- Paid API/service cost: USD 0.
- Heavy local model work: none.
- Screenshot dependency: one PostgreSQL container plus short-lived local API, Vite, and Chromium.
- The first verification accidentally used the existing general `up` dependency and briefly
  started the isolated lab database and Neo4j too; the Make target was immediately corrected to
  start only `app-db` for future runs. No model or lab workload ran.

## 7. Honest limitations and remaining work

- V4 is a small, project-authored synthetic-lab study; 30 variants share 11 captures.
- The 69/69 written claim review is AI-assisted, not independent human validation.
- The v4 model orders observations, while trusted code owns the synthetic-lab diagnosis/citations.
- Scoped core coverage is 85.14%; it is not whole-repository coverage.
- The deterministic screenshots verify product wiring, not model diagnosis quality.
- GitHub workflows remain unpushed/unexecuted remotely; pushing is a separate publication action.
- The full backend image build and Trivy image scan remain assigned to remote CI to avoid a heavy
  laptop run.
- There is no public deployment or production integration.

## 8. Final handoff

There is no next implementation phase in the supplied roadmap. The next optional action is a
separately authorized Git push, followed by inspection of private-repository CI/security results.
Absent that approval, the correct state is a complete local portfolio with two unpushed Phase 10
commits plus the Phase 11 work.
