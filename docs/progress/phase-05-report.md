# Phase 5 Progress Report — Adaptive Investigator and Grounded Reports

Date: 2026-09-23

Status: **IN PROGRESS — deterministic/local implementation ready; real-model gate BLOCKED**

## Scope completed without paid services

- Implemented one typed LangGraph investigator with all 12 required lifecycle nodes.
- Added strict LangChain structured-output model boundaries and a disabled-by-default provider adapter.
- Added eight typed, read-only observation tools with deterministic authorization, cutoff, query-template, payload, and timeout boundaries.
- Added deterministic call, token, cost, tool, round, and active-runtime budget checks.
- Added typed grounded reports, citation resolution, contradiction fields, abstention, and one bounded repair route.
- Added PostgreSQL LangGraph checkpointing plus immutable evidence and report persistence.
- Kept raw telemetry outside checkpoint state. Checkpoints contain evidence IDs, hashes, provenance, and bounded deterministic summaries; the full redacted observation is stored separately.
- Built the incident evaluation manifest with 60 cases: 30 development and 30 held-out, each containing 20 identifiable, 5 insufficient-evidence, and 5 healthy cases.
- Sealed the held-out cases and evaluator labels before model/prompt tuning. Current seal: `1dbac7ea0da7702ad13c387743c2c5c795e45f3d81c78d857a98095cf25d8b67`.
- Demonstrated with deterministic model fixtures that different incidents can select `get_metrics` or `search_logs`, and that absent telemetry produces an inconclusive report.
- Added explicit tests for unauthorized and duplicate tool requests, invalid model boundary output, unavailable citations, and pre-call token-budget rejection.

## Verified commands

```text
make lint
make typecheck
make test
make migrate
make test-investigator-integration
make verify-incident-eval
make investigator-status
```

Observed results:

- Ruff: pass.
- Strict mypy: pass over 19 source files.
- Unit tests: 41 passed; integration tests excluded from this count.
- Global unit-only coverage: 48.17%; the retained 85% later-core target is not yet met.
- Phase 5 integration tests: 2 passed against the real local PostgreSQL checkpointer and immutable evidence/report tables, plus real capture adapters.
- Incident evaluation manifest: 60 total, 30 development, 30 held-out, seal verified, held-out not evaluated.
- Docker services: eight local services healthy at verification time.

## Gate assessment

| Requirement | Result |
|---|---|
| Typed adaptive graph and bounded observation loop | PASS with deterministic fixtures |
| Two evidence-dependent next-tool choices | PASS with deterministic fixtures |
| Actual evidence citations and report validation | PASS |
| Missing telemetry can cause abstention | PASS |
| Call/time/context/tool limits | PASS in implementation and deterministic tests |
| Invalid model output and tool failures | PASS in deterministic tests |
| Persistent checkpointing from the workflow start | PASS against local PostgreSQL |
| Real model calls drive real tools | **BLOCKED** |

The Phase 5 gate is not passed. `MODEL_PROVIDER=disabled`, no paid call is authorized, and no suitable local chat model/runtime is installed. Deterministic fixtures are test evidence, not a substitute for the required real-model integration.

The repository-wide coverage gate also remains open. The 85% target applies to the later core release and is reported as a failure rather than weakened.

## Cost and compute decision

No hosted model call was made and the configured monetary ceiling remains zero. The remaining gate can be attempted later with either:

1. a free local OpenAI-compatible model runtime, after agreeing to its download and laptop resource cost; or
2. a free Colab session, with the user running the heavy model step and returning the generated artifacts.

The held-out incident split must remain unopened until prompts, settings, scoring code, and the approved run plan are frozen in Phase 9.

## Next action

Complete one approved free real-model integration run over development cases only. Do not mark Phase 5 complete until real model output invokes the real read-only tools and produces validated grounded reports under the configured limits.
