# Phase 6 Completion Report — Durable Execution and Human Review

Date: 2026-09-23

Status: **PASS**

Roadmap position: Phase 6 of 11 delivery phases is complete. Including discovery Phase 0, **7 of 12 gates are complete**.

## Scope and resource boundary

Phase 6 was completed without a real model, Ollama, GPU, large download, paid API, or held-out evaluation. Local verification used deterministic model/tool fixtures and only the bounded PostgreSQL `app-db` service (1 CPU and 768 MiB configured memory). The expensive Phase 5 model gate was not repeated.

## Implemented durability contract

- Queue claims carry a lease owner, random lease token, expiry, attempt, generation, task kind, and target report version.
- A server-owned PostgreSQL thread ID binds each investigation to its LangGraph checkpoint history.
- The coordinator selects initial execution, authenticated review resume, review revision, or follow-up exclusively from lease-fenced server state.
- Waiting for human review changes the job to `waiting`, clears its lease, and releases worker capacity.
- A submitted decision is stored before a fresh resume work item is queued. API request handling never owns the resumed model run.
- Report publication, final lifecycle events, and review effects use stable deduplication keys. Delivery remains at-least-once; no exactly-once claim is made.
- Publication rechecks the live lease in the same transaction. A stale worker cannot publish, complete, or overwrite an immutable report version.
- Review decisions require a `reviewer` or `operator` role and are bound to reviewer identity, investigation, immutable report version, expiry, and idempotency key.
- `accept`, `reject`, and `request_revision` are diagnosis-review decisions only. They do not authorize remediation.
- Queued and waiting cancellation is immediate. Running cancellation is cooperative and prevents completion/publication once observed; it cannot reverse an already-issued provider call or charge.
- Follow-ups retain cumulative usage, require an explicit incremental model/tool-call budget, resume the same checkpoint thread, and target a new immutable report version.

## Schema and API boundaries

Migration `003_durability.sql` adds server-owned thread IDs, cumulative usage, cancellation state, generation-aware work items, event deduplication, report publications, review requests/decisions, and follow-up records.

The authenticated API now exposes:

- `POST /api/v1/investigations/{id}/reviews`
- `POST /api/v1/investigations/{id}/cancel`
- `POST /api/v1/investigations/{id}/followups`

Phase 7 will complete the public API assembly and incident console. The existing default CLI worker intentionally remains the non-AI foundation worker; production composition will use `DurableWorkflowCoordinator`.

## Gate evidence

The final lightweight checks were:

```text
.venv/bin/ruff check .
.venv/bin/mypy
.venv/bin/pytest -m 'not integration' -q
RUN_INTEGRATION=1 .venv/bin/pytest tests/integration/test_durable_queue.py -v
RUN_INVESTIGATOR_INTEGRATION=1 .venv/bin/pytest \
  tests/integration/test_phase5_investigator.py \
  -k 'postgres_checkpointer or review_interrupt or queue_lease or budgeted_follow_up' -v
```

Verified result:

- Ruff: pass.
- Strict mypy over 21 source modules: pass.
- Unit tests: 51 passed.
- PostgreSQL queue/recovery tests: 6 passed.
- PostgreSQL checkpoint/coordinator tests: 4 selected and passed.

The tests demonstrate:

1. An expired worker lease is reclaimed and the stale worker cannot complete.
2. A process can stop at a persisted human-review interrupt and a new process can resume it.
3. Queue lease state and checkpoint state coordinate end to end across that restart.
4. Retrying the same report publication or review decision does not duplicate its effect.
5. A stale attempt cannot publish before final publication.
6. Review waiting releases the lease; unauthorized, stale, mismatched, and expired reviews fail closed.
7. Cooperative cancellation blocks completion and transitions the run to `cancelled`.
8. Cumulative usage survives and an explicitly budgeted follow-up publishes report version 2.
9. The coordinator heartbeats an active lease and stops scheduling when cancellation is observed.

## Honest limitations

- Global unit-only coverage is still below the retained 85 percent later-core target.
- The Phase 7 API/console and production worker dependency assembly are not implemented yet.
- Cancellation is cooperative. Work already accepted by an external provider may still finish or incur its already-authorized cost.
- This phase validates execution semantics, not diagnosis quality. The Phase 9 held-out evaluation remains sealed and unexecuted.

## Next phase

Phase 7 is the next unstarted phase and requires explicit user continuation. It will complete the API and incident console on the durable execution contract established here.
