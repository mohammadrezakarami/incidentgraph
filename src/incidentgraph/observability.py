from __future__ import annotations

import json
import re
import threading
from collections.abc import Mapping, MutableMapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.propagate import extract, inject
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from prometheus_client import Counter, Gauge, Histogram

from incidentgraph.config import Settings

_SENSITIVE_KEY = re.compile(
    r"(?i)(authorization|cookie|credential|dsn|password|secret|token|api[_-]?key)"
)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_URI_CREDENTIALS = re.compile(r"(?P<scheme>[a-z][a-z0-9+.-]*://)[^/@\s:]+:[^/@\s]+@", re.I)
_ASSIGNMENT = re.compile(
    r"(?i)\b(password|secret|token|api[_-]?key|authorization)\s*[:=]\s*[^\s,;]+"
)

API_REQUESTS = Counter(
    "incidentgraph_api_requests_total",
    "Bounded API request count.",
    ("method", "route", "status"),
)
API_DURATION = Histogram(
    "incidentgraph_api_request_duration_seconds",
    "API request duration in seconds.",
    ("method", "route"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
WORKER_ATTEMPTS = Counter(
    "incidentgraph_worker_attempts_total",
    "Durable worker attempts by bounded task kind and outcome.",
    ("task_kind", "outcome"),
)
WORKER_DURATION = Histogram(
    "incidentgraph_worker_attempt_duration_seconds",
    "Durable worker attempt duration in seconds.",
    ("task_kind",),
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 180),
)
MODEL_CALLS = Counter(
    "incidentgraph_model_calls_total",
    "Model calls by bounded operation and outcome.",
    ("operation", "outcome"),
)
MODEL_DURATION = Histogram(
    "incidentgraph_model_call_duration_seconds",
    "Model call duration in seconds.",
    ("operation",),
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
)
TOOL_CALLS = Counter(
    "incidentgraph_tool_calls_total",
    "Read-only tool calls by registered tool and outcome.",
    ("tool", "outcome"),
)
TOOL_DURATION = Histogram(
    "incidentgraph_tool_call_duration_seconds",
    "Read-only tool call duration in seconds.",
    ("tool",),
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
PROCESS_RSS_BYTES = Gauge(
    "incidentgraph_process_rss_bytes",
    "Best-effort resident set size for the current process.",
    ("process",),
)

_provider: TracerProvider | None = None
_configured_services: set[str] = set()


def redact(value: Any) -> Any:
    """Redact secrets recursively before values reach logs, traces, or saved diagnostics."""
    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]" if _SENSITIVE_KEY.search(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        result = _BEARER.sub("Bearer [REDACTED]", value)
        result = _URI_CREDENTIALS.sub(r"\g<scheme>[REDACTED]@", result)
        return _ASSIGNMENT.sub(lambda match: f"{match.group(1)}=[REDACTED]", result)
    return value


def redact_structlog(
    _logger: Any, _method_name: str, event_dict: MutableMapping[str, Any]
) -> Mapping[str, Any]:
    redacted = redact(dict(event_dict))
    if not isinstance(redacted, dict):
        return {"event": "[REDACTED]"}
    return redacted


class BoundedJsonlSpanExporter(SpanExporter):
    """Local-only JSONL exporter with rotation, retention, and strict redaction."""

    def __init__(
        self,
        path: Path,
        *,
        max_bytes: int,
        backup_count: int,
        retention_days: int,
    ) -> None:
        self.path = path
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.retention_days = retention_days
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._prune()

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        try:
            records = [json.dumps(self._serialize(span), sort_keys=True) + "\n" for span in spans]
            encoded_size = sum(len(record.encode("utf-8")) for record in records)
            with self._lock:
                self._rotate_if_needed(encoded_size)
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.writelines(records)
            return SpanExportResult.SUCCESS
        except (OSError, TypeError, ValueError):
            return SpanExportResult.FAILURE

    def _serialize(self, span: ReadableSpan) -> dict[str, Any]:
        context = span.get_span_context()
        if context is None:
            raise ValueError("readable span is missing a span context")
        parent = span.parent
        redacted = redact(
            {
                "name": span.name,
                "trace_id": f"{context.trace_id:032x}",
                "span_id": f"{context.span_id:016x}",
                "parent_span_id": f"{parent.span_id:016x}" if parent is not None else None,
                "start_time": _nanoseconds_to_iso(span.start_time),
                "end_time": _nanoseconds_to_iso(span.end_time),
                "status": span.status.status_code.name,
                "attributes": dict(span.attributes or {}),
                "events": [
                    {"name": event.name, "attributes": dict(event.attributes or {})}
                    for event in span.events
                ],
            }
        )
        if not isinstance(redacted, dict):
            raise ValueError("serialized span must remain a mapping")
        return redacted

    def _rotate_if_needed(self, incoming_bytes: int) -> None:
        if self.path.exists() and self.path.stat().st_size + incoming_bytes <= self.max_bytes:
            return
        oldest = self.path.with_suffix(self.path.suffix + f".{self.backup_count}")
        if oldest.exists():
            oldest.unlink()
        for index in range(self.backup_count - 1, 0, -1):
            source = self.path.with_suffix(self.path.suffix + f".{index}")
            if source.exists():
                source.replace(self.path.with_suffix(self.path.suffix + f".{index + 1}"))
        if self.path.exists():
            self.path.replace(self.path.with_suffix(self.path.suffix + ".1"))

    def _prune(self) -> None:
        cutoff = datetime.now(UTC) - timedelta(days=self.retention_days)
        for candidate in self.path.parent.glob(f"{self.path.name}*"):
            modified = datetime.fromtimestamp(candidate.stat().st_mtime, tz=UTC)
            if modified < cutoff:
                candidate.unlink()


def _nanoseconds_to_iso(value: int | None) -> str | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value / 1_000_000_000, tz=UTC).isoformat()


def configure_observability(settings: Settings, service_name: str) -> None:
    """Enable the optional local exporter. The default remains metrics-only."""
    global _provider
    if not settings.observability_tracing_enabled or service_name in _configured_services:
        return
    if _provider is None:
        _provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
        trace.set_tracer_provider(_provider)
    path = settings.observability_trace_dir / f"{service_name}.jsonl"
    _provider.add_span_processor(
        SimpleSpanProcessor(
            BoundedJsonlSpanExporter(
                path,
                max_bytes=settings.observability_trace_max_bytes,
                backup_count=settings.observability_trace_backup_count,
                retention_days=settings.observability_trace_retention_days,
            )
        )
    )
    _configured_services.add(service_name)


def tracer() -> trace.Tracer:
    return trace.get_tracer("incidentgraph", "0.1.0")


def current_traceparent() -> str | None:
    carrier: dict[str, str] = {}
    inject(carrier)
    return carrier.get("traceparent")


def parent_context(traceparent: str | None) -> Context | None:
    if not traceparent:
        return None
    return extract({"traceparent": traceparent})


def record_api_request(method: str, route: str, status_code: int, duration: float) -> None:
    status = str(status_code // 100) + "xx"
    API_REQUESTS.labels(method, route, status).inc()
    API_DURATION.labels(method, route).observe(duration)


def record_worker_attempt(task_kind: str, outcome: str, duration: float) -> None:
    WORKER_ATTEMPTS.labels(task_kind, outcome).inc()
    WORKER_DURATION.labels(task_kind).observe(duration)


def record_model_call(operation: str, outcome: str, duration: float) -> None:
    MODEL_CALLS.labels(operation, outcome).inc()
    MODEL_DURATION.labels(operation).observe(duration)


def record_tool_call(tool: str, outcome: str, duration: float) -> None:
    TOOL_CALLS.labels(tool, outcome).inc()
    TOOL_DURATION.labels(tool).observe(duration)


def observe_process_rss(process: str) -> None:
    try:
        import resource

        rss = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        # macOS reports bytes; Linux reports KiB.
        if rss < 10_000_000:
            rss *= 1024
        PROCESS_RSS_BYTES.labels(process).set(rss)
    except (ImportError, OSError, ValueError):
        return
