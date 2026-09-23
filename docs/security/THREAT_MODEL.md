# IncidentGraph Threat Model

Status: Phase 7 local-release baseline  
Last reviewed: 2026-09-23

## Scope and trust boundaries

IncidentGraph is a local, single-operator laboratory application. It is not a multi-tenant
identity platform and must not be exposed to the public Internet. The browser talks only to the
loopback FastAPI origin. The API and worker share the application PostgreSQL database; the worker
alone calls the approved model provider and read-only observation adapters. Neo4j, Prometheus,
Redis, the lab database, and fault controls remain on internal Compose networks or loopback.

The following inputs are untrusted even when they originate inside the lab: user questions,
browser fields, corpus text, retrieved documents, logs, telemetry labels, model output, and tool
output. Evaluator labels and fault-control settings are outside the agent runtime boundary.

## Assets

- Bearer tokens, model-provider credentials, and database credentials.
- Investigation ownership, reports, evidence, events, reviews, and checkpoints.
- Corpus provenance, topology validity intervals, replay cutoffs, and evaluator-only labels.
- Queue leases, fencing tokens, budgets, and cancellation state.

## Actors and access

- `viewer`: may create and read only its own investigations and authorized services.
- `reviewer`: may decide a pending report only after the API separately proves ownership.
- `operator`: may inspect or operate across investigation owners and access internal metrics.
- API: validates identity, ownership, bounds, identifiers, timestamps, and request shape.
- Worker: leases durable jobs and invokes only registered read-only tools.
- Model provider: receives bounded, redacted context only when explicitly configured.

Development bearer tokens are high-entropy values stored only as SHA-256 hashes in server
configuration. This is deliberately simpler than enterprise identity. Tokens are sent in the
`Authorization` header, never a URL. The browser keeps the token in memory rather than persistent
storage. An SSE connection authenticates at establishment and is capped at five minutes; reconnect
reauthenticates, so token rotation/revocation takes effect no later than reconnect. Existing local
tokens do not carry an intrinsic expiry claim.

## Threats and controls

| Threat | Required control |
|---|---|
| Cross-user record access | Owner predicate on every lookup/stream/mutation; only explicit operator bypass; indistinguishable 404 where appropriate |
| Forged or stale review | Reviewer/operator role, owner/operator scope, report-version match, expiry, idempotency key, durable decision record |
| Duplicate/replayed creation | Per-owner idempotency key and server-generated identifiers |
| Stale worker publication | Lease owner/token/expiry/generation/report-version fencing and atomic publication |
| Prompt or corpus injection | Model cannot add tools or permissions; registered typed read-only tools recheck authorization; strict model-output validation |
| SSRF, arbitrary query, path traversal, shell execution | No general URL, filesystem, Cypher, PromQL, shell, Docker, or fault-control tool is exposed to the investigator |
| Evaluator-label leakage | Labels excluded from runtime image/mounts and never returned by observation adapters |
| Oversized or abusive requests | Pydantic bounds, request-size cap, pagination, per-principal local rate limit, bounded graph/event depth |
| Browser token leakage | Authorization header only, restrictive CORS, no query token, no persistent token storage, safe text rendering |
| Stored XSS | React text rendering; no raw HTML or executable Markdown rendering |
| Secret leakage through telemetry | Structured allow-listed fields and redaction; credentials are never placed in report/evidence/checkpoint payloads |
| Unsafe cancellation claim | Cooperative stop only; already-issued provider requests or charges cannot be reversed |
| Dependency outage | Readiness and consistent retryable errors; no silent fake-model fallback |

The local in-process rate limiter is a bounded-development control, not a distributed security
gateway. Neo4j Community credentials and application-side query templates are also residual risks:
read routing does not itself make a privileged credential read-only. Public deployment would
require an external identity provider, TLS, centralized rate limiting, secret rotation, database
least privilege, and a separate deployment threat review.

## Verification mapping

- API contract tests cover missing/invalid authentication, cross-user reads and mutations,
  operator-only metrics, request IDs, pagination, body limits, and SSE resume without duplication.
- PostgreSQL integration tests cover durable ownership predicates, idempotency, stale reviews,
  cancellation, follow-ups, and fencing.
- Playwright covers token-in-header use, refresh/reconnect, citation drill-down, review meaning,
  and a rejected cross-user browser request against the real API.
- Phase 8 adds prompt-injection, redaction, dependency-outage, retention, and resource-bound tests.

Passing these tests shows the named controls worked for the tested cases; it is not proof of
universal prompt-injection resistance or production-grade multi-tenant security.
