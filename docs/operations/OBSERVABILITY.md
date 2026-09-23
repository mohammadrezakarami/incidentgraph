# IncidentGraph Observability Operations

Status: Phase 8 local-release contract
Last verified: 2026-09-23

## Scope

IncidentGraph exposes bounded Prometheus metrics and can optionally write correlated OpenTelemetry
spans to local rotating JSONL files. No external collector, account, or paid service is required.
Tracing is disabled by default so enabling it is an explicit local data-retention decision.

## Correlation path

The API starts `incidentgraph.api.request`, injects a W3C `traceparent`, and stores that value with
the investigation in PostgreSQL. A leased worker extracts the server-stored parent and creates
`incidentgraph.worker.attempt`. Model and registered read-only tool calls create child spans named
`incidentgraph.model.call` and `incidentgraph.tool.call`. Follow-up and review jobs reuse the
investigation-level parent rather than trusting browser-supplied resume context.

Trace attributes contain bounded identifiers, route templates, registered operation/tool names,
outcomes, durations, and token counts. They do not contain bearer tokens, prompts, questions, raw
evidence, model responses, database DSNs, or tool arguments.

## Enable local tracing

Set these values in the untracked `.env`:

```text
INCIDENTGRAPH_OBSERVABILITY_TRACING_ENABLED=true
INCIDENTGRAPH_OBSERVABILITY_TRACE_DIR=data/runtime/app-traces
INCIDENTGRAPH_OBSERVABILITY_TRACE_MAX_BYTES=2000000
INCIDENTGRAPH_OBSERVABILITY_TRACE_BACKUP_COUNT=3
INCIDENTGRAPH_OBSERVABILITY_TRACE_RETENTION_DAYS=7
```

Restart API and worker processes after changing the setting. Files are written separately per
process and remain under the ignored runtime directory. Rotation is size-bounded and old trace
files are pruned when an exporter starts. Redaction is applied before serialization.

## Prometheus metrics

An authenticated operator can read `/metrics`. The Phase 8 application series are:

- `incidentgraph_api_requests_total` and `incidentgraph_api_request_duration_seconds`
- `incidentgraph_worker_attempts_total` and `incidentgraph_worker_attempt_duration_seconds`
- `incidentgraph_model_calls_total` and `incidentgraph_model_call_duration_seconds`
- `incidentgraph_tool_calls_total` and `incidentgraph_tool_call_duration_seconds`
- `incidentgraph_process_rss_bytes`

Labels are selected from bounded enums or route templates. Investigation IDs, request IDs, user
questions, and exception messages are never metric labels.

## Retention and profiling

Preview expired persisted events without deleting them:

```bash
make retention-status
```

Actual deletion requires the explicit command below; it deletes only event rows older than
`INCIDENTGRAPH_EVENT_RETENTION_DAYS` and does not delete investigations, evidence, reports,
reviews, or checkpoints:

```bash
.tools/uv run incidentgraph retention --apply
```

Create the lightweight local profile without invoking a model or load generator:

```bash
.venv/bin/python scripts/phase8_profile.py
```

The versioned result is `artifacts/observability/phase8-local-profile.json`. It is a point-in-time
development-machine observation, not a capacity benchmark or production SLO.

## Failure semantics

An unavailable read-only source returns a typed `UNAVAILABLE`, `NOT_FOUND`, or `TIMEOUT` tool
result without embedding the original exception text. Tracing failure never grants authority,
changes the tool registry, or enables a fallback model. The durable investigation remains subject
to its existing call, round, time, token, cost, authorization, and observation-window bounds.
