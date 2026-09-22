from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Lock
from typing import Any, Literal

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace import Tracer
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    ProcessCollector,
)
from pydantic import BaseModel, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LabServiceName = Literal["gateway", "checkout", "payments"]
FaultKind = Literal[
    "latency",
    "pool_exhaustion",
    "dependency_errors",
    "cache_degradation",
    "deployment_regression",
    "resource_contention",
    "metrics_disabled",
]


class LabServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LAB_", extra="ignore")

    service: LabServiceName
    environment: Literal["lab"] = "lab"
    port: int = Field(default=8080, ge=1024, le=65535)
    checkout_url: str = "http://checkout:8080"
    payments_url: str = "http://payments:8080"
    database_dsn: SecretStr
    redis_url: str = "redis://redis:6379/0"
    control_token: SecretStr = Field(min_length=32)
    log_dir: Path = Path("/var/log/incidentgraph")
    trace_dir: Path = Path("/var/traces/incidentgraph")
    deployment_version: str = Field(default="v1.0.0", pattern=r"^[a-zA-Z0-9._-]+$")
    http_timeout_seconds: float = Field(default=1.0, ge=0.2, le=5.0)
    db_pool_size: int = Field(default=4, ge=2, le=8)
    db_pool_timeout_seconds: float = Field(default=0.25, ge=0.05, le=2.0)
    fault_max_seconds: int = Field(default=30, ge=5, le=60)


class FaultCommand(BaseModel):
    kind: FaultKind
    duration_seconds: int = Field(ge=2, le=30)
    seed: int = Field(default=1, ge=0, le=2_147_483_647)
    delay_ms: int = Field(default=0, ge=0, le=500)
    error_rate: float = Field(default=0, ge=0, le=0.9)
    hold_connections: int = Field(default=0, ge=0, le=8)
    cpu_ms: int = Field(default=0, ge=0, le=200)
    deployment_version: str | None = Field(
        default=None,
        pattern=r"^[a-zA-Z0-9._-]+$",
    )

    @model_validator(mode="after")
    def validate_parameters(self) -> FaultCommand:
        requirements: dict[FaultKind, tuple[str, float | int | str | None]] = {
            "latency": ("delay_ms", self.delay_ms),
            "pool_exhaustion": ("hold_connections", self.hold_connections),
            "dependency_errors": ("error_rate", self.error_rate),
            "cache_degradation": ("kind", self.kind),
            "deployment_regression": ("deployment_version", self.deployment_version),
            "resource_contention": ("cpu_ms", self.cpu_ms),
            "metrics_disabled": ("kind", self.kind),
        }
        name, value = requirements[self.kind]
        if value in {None, 0, ""}:
            raise ValueError(f"{name} is required for {self.kind}")
        return self


@dataclass(frozen=True)
class ActiveFault:
    command: FaultCommand
    applied_at: datetime
    expires_monotonic: float

    @property
    def expires_at(self) -> datetime:
        remaining = max(0.0, self.expires_monotonic - time.monotonic())
        return datetime.fromtimestamp(self.applied_at.timestamp() + remaining, tz=UTC)


class FaultState:
    def __init__(self, max_duration_seconds: int) -> None:
        self._max_duration_seconds = max_duration_seconds
        self._active: ActiveFault | None = None
        self._lock = Lock()

    def apply(self, command: FaultCommand) -> ActiveFault:
        if command.duration_seconds > self._max_duration_seconds:
            raise ValueError("fault duration exceeds the configured service maximum")
        active = ActiveFault(
            command=command,
            applied_at=datetime.now(UTC),
            expires_monotonic=time.monotonic() + command.duration_seconds,
        )
        with self._lock:
            self._active = active
        return active

    def current(self) -> ActiveFault | None:
        with self._lock:
            active = self._active
            if active is not None and time.monotonic() >= active.expires_monotonic:
                self._active = None
                return None
            return active

    def reset(self) -> None:
        with self._lock:
            self._active = None


class JsonLineSpanExporter(SpanExporter):
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._lock = Lock()

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        rows = []
        for span in spans:
            context = span.get_span_context()
            parent = span.parent
            trace_id = f"{context.trace_id:032x}" if context is not None else None
            span_id = f"{context.span_id:016x}" if context is not None else None
            rows.append(
                json.dumps(
                    {
                        "name": span.name,
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": f"{parent.span_id:016x}" if parent else None,
                        "start_time": _nanoseconds_to_iso(span.start_time),
                        "end_time": _nanoseconds_to_iso(span.end_time),
                        "status": span.status.status_code.name,
                        "attributes": dict(span.attributes or {}),
                    },
                    sort_keys=True,
                    default=str,
                )
            )
        with self._lock, self._path.open("a", encoding="utf-8") as stream:
            for row in rows:
                stream.write(row + "\n")
        return SpanExportResult.SUCCESS


def _nanoseconds_to_iso(value: int | None) -> str | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value / 1_000_000_000, tz=UTC).isoformat()


def build_tracer(service: LabServiceName, trace_dir: Path) -> Tracer:
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": service,
                "deployment.environment": "lab",
            }
        )
    )
    provider.add_span_processor(
        SimpleSpanProcessor(JsonLineSpanExporter(trace_dir / f"{service}.jsonl"))
    )
    return provider.get_tracer("incidentgraph.lab")


def build_event_logger(service: LabServiceName, log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(f"incidentgraph.lab.{service}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()
    handler = RotatingFileHandler(
        log_dir / f"{service}.jsonl",
        maxBytes=5 * 1024 * 1024,
        backupCount=2,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    return logger


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    payload = {
        "timestamp": datetime.now(UTC).isoformat(),
        "severity": "INFO",
        "event": event,
        **fields,
    }
    logger.info(json.dumps(payload, sort_keys=True, default=str))


class LabMetrics:
    def __init__(self, service: LabServiceName, deployment_version: str) -> None:
        self.service = service
        self.registry = CollectorRegistry()
        ProcessCollector(registry=self.registry)
        self.requests = Counter(
            "lab_http_requests_total",
            "Completed HTTP requests.",
            ["service", "route", "status_class"],
            registry=self.registry,
        )
        self.request_duration = Histogram(
            "lab_http_request_duration_seconds",
            "HTTP request duration in seconds.",
            ["service", "route"],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0),
            registry=self.registry,
        )
        self.outbound = Counter(
            "lab_outbound_requests_total",
            "Outbound dependency calls.",
            ["service", "dependency", "outcome"],
            registry=self.registry,
        )
        self.outbound_duration = Histogram(
            "lab_outbound_request_duration_seconds",
            "Outbound dependency duration in seconds.",
            ["service", "dependency"],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0),
            registry=self.registry,
        )
        self.db_pool_size = Gauge(
            "lab_db_pool_size",
            "Configured database pool size.",
            ["service"],
            registry=self.registry,
        )
        self.db_pool_in_use = Gauge(
            "lab_db_pool_in_use",
            "Database connections currently in use.",
            ["service"],
            registry=self.registry,
        )
        self.db_pool_wait = Histogram(
            "lab_db_pool_wait_seconds",
            "Database connection acquisition wait in seconds.",
            ["service"],
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5),
            registry=self.registry,
        )
        self.db_pool_timeouts = Counter(
            "lab_db_pool_timeouts_total",
            "Database pool acquisition timeouts.",
            ["service"],
            registry=self.registry,
        )
        self.cache = Counter(
            "lab_cache_requests_total",
            "Cache requests by result.",
            ["service", "result"],
            registry=self.registry,
        )
        self.deployment = Gauge(
            "lab_deployment_info",
            "Active deployment version.",
            ["service", "version"],
            registry=self.registry,
        )
        self.db_pool_size.labels(service).set(0)
        self.db_pool_in_use.labels(service).set(0)
        self.deployment.labels(service, deployment_version).set(1)
        self._deployment_version = deployment_version

    def set_pool_size(self, size: int) -> None:
        self.db_pool_size.labels(self.service).set(size)

    def set_deployment(self, version: str) -> None:
        self.deployment.labels(self.service, self._deployment_version).set(0)
        self.deployment.labels(self.service, version).set(1)
        self._deployment_version = version


def verify_control_token(supplied: str | None, expected: SecretStr) -> bool:
    if supplied is None:
        return False
    supplied_hash = hashlib.sha256(supplied.encode()).digest()
    expected_hash = hashlib.sha256(expected.get_secret_value().encode()).digest()
    return hmac.compare_digest(supplied_hash, expected_hash)


def span_context_fields() -> Mapping[str, str]:
    context = trace.get_current_span().get_span_context()
    if not context.is_valid:
        return {"trace_id": "", "span_id": ""}
    return {
        "trace_id": f"{context.trace_id:032x}",
        "span_id": f"{context.span_id:016x}",
    }


def bounded_cpu_work(milliseconds: int) -> int:
    deadline = time.perf_counter() + milliseconds / 1_000
    value = 0
    while time.perf_counter() < deadline:
        value = (value * 33 + 17) % 1_000_003
    return value


def first_header(headers: Mapping[str, str], names: Iterable[str]) -> str | None:
    for name in names:
        value = headers.get(name)
        if value:
            return value
    return None
