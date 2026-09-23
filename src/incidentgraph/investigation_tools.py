from __future__ import annotations

import asyncio
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import NAMESPACE_URL, uuid5

from neo4j import GraphDatabase
from pydantic import ValidationError

from incidentgraph.config import Settings
from incidentgraph.ingestion import ROOT, load_topology
from incidentgraph.investigator import (
    TOOL_INPUTS,
    ChangesInput,
    DependenciesInput,
    Direction,
    LogsInput,
    MetricsInput,
    ResolveServiceInput,
    RetrieveInput,
    ServiceContextInput,
    ToolName,
    ToolRequest,
    ToolResult,
    ToolRuntimeContext,
)
from incidentgraph.models import EvidenceItem
from incidentgraph.retrieval import Neo4jRetriever, RetrievalRequest, RetrievalVariant

CAPTURE_ROOT = ROOT / "data" / "captures"
SNAPSHOT_PATTERN = re.compile(r"^cap-[a-zA-Z0-9-]{8,80}$")
REDACTED_KEYS = re.compile(r"(?i)(authorization|token|password|secret|api[_-]?key|cookie)")
MAX_SERIALIZED_EVIDENCE_BYTES = 64_000
MAX_METRIC_SERIES = 20
MAX_METRIC_POINTS = 600


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if REDACTED_KEYS.search(str(key)) else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key, "unknown"))
        counts[value] = counts.get(value, 0) + 1
    return counts


def _metric_summary(series: dict[str, Any]) -> dict[str, Any]:
    points = series.get("values", [])
    numeric = [float(point[1]) for point in points if len(point) >= 2]
    return {
        "template_source": series.get("template_source"),
        "metric": series.get("metric", {}),
        "point_count": len(points),
        "first_value": numeric[0] if numeric else None,
        "last_value": numeric[-1] if numeric else None,
        "minimum": min(numeric) if numeric else None,
        "maximum": max(numeric) if numeric else None,
        "unit": {
            "request_latency_p95": "seconds",
            "request_rate": "requests/second",
            "dependency_outcomes": "requests/second",
            "db_pool_in_use": "connections",
            "db_pool_timeouts": "timeouts/10_seconds",
            "cache_outcomes": "requests/second",
            "process_cpu": "cpu_seconds/second",
        }.get(str(series.get("template_source")), "unknown"),
    }


class CaptureToolbox:
    """Read-only adapters over immutable lab captures, Neo4j, and Phase 4 retrieval."""

    def __init__(self, settings: Settings, capture_root: Path = CAPTURE_ROOT) -> None:
        self.settings = settings
        self.capture_root = capture_root.resolve()

    def _capture_dir(self, snapshot_id: str | None) -> Path:
        if snapshot_id is None or not SNAPSHOT_PATTERN.fullmatch(snapshot_id):
            raise ValueError("a valid opaque replay snapshot_id is required")
        path = (self.capture_root / snapshot_id).resolve()
        if self.capture_root not in path.parents or not path.is_dir():
            raise FileNotFoundError("replay snapshot was not found")
        return path

    @staticmethod
    def _validate_request(request: ToolRequest) -> Any:
        return TOOL_INPUTS[request.tool].model_validate(request.arguments)

    def _evidence(
        self,
        *,
        context: ToolRuntimeContext,
        tool: ToolName,
        source_id: str,
        kind: str,
        service_ids: list[str],
        content: Any,
        limitations: list[str] | None = None,
        unit: str | None = None,
        aggregation: str | None = None,
    ) -> EvidenceItem:
        serialized = _json(_redact(content))
        if len(serialized.encode()) > MAX_SERIALIZED_EVIDENCE_BYTES:
            raise ValueError("normalized evidence exceeds the 64 KB bound")
        identity = (
            f"{context.investigation_id}|{context.snapshot_id}|{tool}|"
            f"{source_id}|{_sha256(serialized)}"
        )
        return EvidenceItem(
            evidence_id=uuid5(NAMESPACE_URL, f"incidentgraph://observation/{identity}"),
            kind=cast(Any, kind),
            source_id=source_id,
            source_version="1",
            service_ids=service_ids,
            environment=context.environment,
            observed_at=context.observation_cutoff,
            collected_at=datetime.now(UTC),
            content_hash=_sha256(serialized),
            freshness_status="fresh",
            limitations=limitations or ["laboratory evidence, not production evidence"],
            provenance_reference=(f"capture://{context.snapshot_id}/{source_id};tool={tool.value}"),
            window_start=context.window_start,
            window_end=context.window_end,
            valid_from=context.window_start,
            valid_to=None,
            snapshot_id=context.snapshot_id,
            query_template_id=f"phase5-{tool.value}-v1",
            safe_parameters={"source_id": source_id, "service_ids": service_ids},
            content=serialized,
            unit=unit,
            aggregation=aggregation,
        )

    async def execute(self, request: ToolRequest, context: ToolRuntimeContext) -> ToolResult:
        try:
            value = self._validate_request(request)
            if request.tool == ToolName.RESOLVE_SERVICE:
                return self._resolve_service(cast(ResolveServiceInput, value), context)
            if request.tool == ToolName.GET_SERVICE_CONTEXT:
                return self._service_context(cast(ServiceContextInput, value), context)
            if request.tool == ToolName.GET_DEPENDENCIES:
                return await asyncio.to_thread(
                    self._dependencies, cast(DependenciesInput, value), context
                )
            if request.tool == ToolName.GET_METRICS:
                return self._metrics(cast(MetricsInput, value), context)
            if request.tool == ToolName.SEARCH_LOGS:
                return self._logs(cast(LogsInput, value), context)
            if request.tool == ToolName.GET_RECENT_CHANGES:
                return self._changes(cast(ChangesInput, value), context)
            if request.tool in {
                ToolName.RETRIEVE_RUNBOOKS,
                ToolName.GET_REVIEWED_INCIDENTS,
            }:
                return await asyncio.to_thread(
                    self._retrieve, request.tool, cast(RetrieveInput, value), context
                )
            raise ValueError(f"unsupported tool: {request.tool}")
        except ValidationError as exc:
            return ToolResult(
                tool=request.tool,
                status="error",
                summary=f"invalid tool arguments: {exc}",
                error_code="INVALID_ARGUMENT",
            )
        except FileNotFoundError as exc:
            return ToolResult(
                tool=request.tool,
                status="error",
                summary=str(exc),
                error_code="NOT_FOUND",
            )
        except ValueError as exc:
            return ToolResult(
                tool=request.tool,
                status="error",
                summary=str(exc),
                error_code="INVALID_ARGUMENT",
            )
        except Exception as exc:
            return ToolResult(
                tool=request.tool,
                status="error",
                summary=f"read-only source unavailable: {type(exc).__name__}",
                error_code="UNAVAILABLE",
            )

    def _resolve_service(
        self, value: ResolveServiceInput, context: ToolRuntimeContext
    ) -> ToolResult:
        matches = [
            item
            for item in load_topology().services
            if item.environment == value.environment
            and value.name.lower()
            in {item.id.lower(), item.name.lower(), *(alias.lower() for alias in item.aliases)}
        ]
        if not matches:
            return ToolResult(
                tool=ToolName.RESOLVE_SERVICE,
                status="error",
                summary="service was not found",
                error_code="NOT_FOUND",
            )
        if len(matches) > 1:
            return ToolResult(
                tool=ToolName.RESOLVE_SERVICE,
                status="error",
                summary="service name is ambiguous",
                error_code="AMBIGUOUS_SERVICE",
            )
        service = matches[0]
        if service.id not in context.authorized_service_ids:
            return ToolResult(
                tool=ToolName.RESOLVE_SERVICE,
                status="error",
                summary="resolved service is outside authorization",
                error_code="UNAUTHORIZED",
            )
        return ToolResult(
            tool=ToolName.RESOLVE_SERVICE,
            status="ok",
            summary=f"resolved {value.name} to {service.id}",
            data={"service_id": service.id, "name": service.name},
        )

    def _service_context(
        self, value: ServiceContextInput, context: ToolRuntimeContext
    ) -> ToolResult:
        service = next(
            (item for item in load_topology().services if item.id == value.service_id), None
        )
        if service is None:
            return ToolResult(
                tool=ToolName.GET_SERVICE_CONTEXT,
                status="error",
                summary="service context was not found",
                error_code="NOT_FOUND",
            )
        data = service.model_dump(mode="json")
        evidence = self._evidence(
            context=context,
            tool=ToolName.GET_SERVICE_CONTEXT,
            source_id="config/topology.json",
            kind="topology",
            service_ids=[service.id],
            content=data,
        )
        return ToolResult(
            tool=ToolName.GET_SERVICE_CONTEXT,
            status="ok",
            summary=f"loaded reviewed context for {service.id}",
            evidence=(evidence,),
            data=data,
        )

    def _dependencies(self, value: DependenciesInput, context: ToolRuntimeContext) -> ToolResult:
        pattern = {
            Direction.OUTBOUND: "-[rels:DEPENDS_ON*1..2]->",
            Direction.INBOUND: "<-[rels:DEPENDS_ON*1..2]-",
            Direction.BOTH: "-[rels:DEPENDS_ON*1..2]-",
        }[value.direction]
        query = (
            "MATCH path=(source:Service {id: $service_id, environment: $environment})"
            f"{pattern}(neighbor:Service) "
            "WHERE length(path) <= $depth "
            "AND all(rel IN rels WHERE rel.valid_from <= $cutoff "
            "AND (rel.valid_to IS NULL OR $cutoff < rel.valid_to)) "
            "RETURN [node IN nodes(path) | node.id] AS nodes, "
            "[rel IN relationships(path) | {type:type(rel), caller:startNode(rel).id, "
            "callee:endNode(rel).id, source_id:rel.source_id, "
            "topology_version:rel.topology_version}] AS relationships, length(path) AS hops "
            "ORDER BY hops LIMIT 50"
        )
        driver = GraphDatabase.driver(
            self.settings.neo4j_uri,
            auth=(self.settings.neo4j_user, self.settings.neo4j_password.get_secret_value()),
        )
        try:
            with driver.session() as session:
                paths = [
                    dict(row)
                    for row in session.run(
                        query,
                        service_id=value.service_id,
                        environment=context.environment,
                        depth=value.depth,
                        cutoff=_iso(value.observation_time),
                    )
                ]
        finally:
            driver.close()
        paths = [
            path
            for path in paths
            if len(path["nodes"]) == len(set(path["nodes"]))
            and set(path["nodes"]).issubset(context.authorized_service_ids)
        ]
        evidence = self._evidence(
            context=context,
            tool=ToolName.GET_DEPENDENCIES,
            source_id="declared-compose-topology-v1",
            kind="topology",
            service_ids=sorted({node for path in paths for node in path["nodes"]}),
            content=paths,
        )
        return ToolResult(
            tool=ToolName.GET_DEPENDENCIES,
            status="ok",
            summary=f"returned {len(paths)} authorized dependency paths",
            evidence=(evidence,),
            data={
                "path_count": len(paths),
                "nodes": sorted({node for path in paths for node in path["nodes"]}),
                "relationships": sorted(
                    {
                        f"{rel['caller']}->{rel['callee']}"
                        for path in paths
                        for rel in path["relationships"]
                    }
                ),
            },
        )

    def _metrics(self, value: MetricsInput, context: ToolRuntimeContext) -> ToolResult:
        capture = self._capture_dir(context.snapshot_id)
        raw = json.loads((capture / "metrics.json").read_text(encoding="utf-8"))
        template_keys = {
            "request_latency": ("request_latency_p95", "request_rate"),
            "error_rate": ("dependency_outcomes",),
            "db_pool": ("db_pool_in_use", "db_pool_timeouts"),
            "cache_outcomes": ("cache_outcomes",),
            "cpu_time": ("process_cpu",),
        }[value.template]
        available_keys = [key for key in template_keys if key in raw]
        if not available_keys:
            return ToolResult(
                tool=ToolName.GET_METRICS,
                status="error",
                summary=f"metric template {value.template} is absent from the snapshot",
                error_code="INSUFFICIENT_DATA",
            )
        bounded: list[dict[str, Any]] = []
        service_name = value.service_id.removeprefix("svc-")
        for metric_key in available_keys:
            results = raw[metric_key].get("data", {}).get("result", [])[:MAX_METRIC_SERIES]
            for series in results:
                labels = series.get("metric", {})
                if labels.get("service") not in {None, service_name}:
                    continue
                points = series.get("values", [])[:MAX_METRIC_POINTS]
                bounded.append({"template_source": metric_key, "metric": labels, "values": points})
        if not bounded:
            return ToolResult(
                tool=ToolName.GET_METRICS,
                status="error",
                summary="no authorized metric series matched the request",
                error_code="INSUFFICIENT_DATA",
            )
        content = {"template": value.template, "series": bounded}
        evidence = self._evidence(
            context=context,
            tool=ToolName.GET_METRICS,
            source_id=f"metrics.json#{value.template}",
            kind="metric",
            service_ids=[value.service_id],
            content=content,
            unit="template-specific; labels retained",
            aggregation="captured Prometheus range-query values",
        )
        return ToolResult(
            tool=ToolName.GET_METRICS,
            status="ok",
            summary=f"returned {len(bounded)} bounded metric series",
            evidence=(evidence,),
            data={
                "template": value.template,
                "series_count": len(bounded),
                "point_count": sum(len(series.get("values", [])) for series in bounded),
                "series_summaries": [_metric_summary(series) for series in bounded],
            },
        )

    def _logs(self, value: LogsInput, context: ToolRuntimeContext) -> ToolResult:
        capture = self._capture_dir(context.snapshot_id)
        allowed_names = {item.removeprefix("svc-") for item in value.service_ids}
        events: list[dict[str, Any]] = []
        for line in (capture / "logs.jsonl").read_text(encoding="utf-8").splitlines():
            item = json.loads(line)
            timestamp = datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00"))
            if item.get("service") not in allowed_names:
                continue
            if not (value.window_start <= timestamp <= value.window_end):
                continue
            if value.severity and item.get("severity") != value.severity:
                continue
            if value.event and item.get("event") != value.event:
                continue
            if value.trace_id and item.get("trace_id") != value.trace_id:
                continue
            events.append(cast(dict[str, Any], _redact(item)))
            if len(events) == value.limit:
                break
        if not events:
            return ToolResult(
                tool=ToolName.SEARCH_LOGS,
                status="error",
                summary="no log events matched the safe filters",
                error_code="INSUFFICIENT_DATA",
            )
        evidence = self._evidence(
            context=context,
            tool=ToolName.SEARCH_LOGS,
            source_id="logs.jsonl",
            kind="log",
            service_ids=list(value.service_ids),
            content=events,
            limitations=["bounded and redacted laboratory log selection"],
        )
        return ToolResult(
            tool=ToolName.SEARCH_LOGS,
            status="ok",
            summary=f"returned {len(events)} redacted log events",
            evidence=(evidence,),
            data={
                "event_count": len(events),
                "services": _count_by(events, "service"),
                "severities": _count_by(events, "severity"),
                "event_types": _count_by(events, "event"),
                "status_codes": _count_by(events, "status_code"),
                "trace_ids": sorted(
                    {str(item["trace_id"]) for item in events if item.get("trace_id")}
                )[:10],
            },
        )

    def _changes(self, value: ChangesInput, context: ToolRuntimeContext) -> ToolResult:
        capture = self._capture_dir(context.snapshot_id)
        changes = json.loads((capture / "changes.json").read_text(encoding="utf-8"))
        allowed_names = {item.removeprefix("svc-") for item in value.service_ids}
        matches = [
            item
            for item in changes
            if item.get("service") in allowed_names
            and value.window_start
            <= datetime.fromisoformat(item["observed_at"].replace("Z", "+00:00"))
            <= value.window_end
        ][:100]
        if not matches:
            return ToolResult(
                tool=ToolName.GET_RECENT_CHANGES,
                status="error",
                summary="no approved changes exist in the requested snapshot window",
                error_code="INSUFFICIENT_DATA",
            )
        evidence = self._evidence(
            context=context,
            tool=ToolName.GET_RECENT_CHANGES,
            source_id="changes.json",
            kind="change",
            service_ids=list(value.service_ids),
            content=matches,
        )
        return ToolResult(
            tool=ToolName.GET_RECENT_CHANGES,
            status="ok",
            summary=f"returned {len(matches)} approved change events",
            evidence=(evidence,),
            data={
                "change_count": len(matches),
                "changes": [
                    {
                        key: item.get(key)
                        for key in ("service", "version", "change_type", "observed_at")
                        if key in item
                    }
                    for item in matches
                ],
            },
        )

    def _retrieve(
        self,
        tool: ToolName,
        value: RetrieveInput,
        context: ToolRuntimeContext,
    ) -> ToolResult:
        target = value.service_ids[0]
        request = RetrievalRequest(
            question=value.query,
            target_service=target,
            environment=context.environment,
            cutoff=value.cutoff,
            authorized_service_ids=context.authorized_service_ids,
            variant=RetrievalVariant(value.variant),
        )
        with Neo4jRetriever(self.settings) as retriever:
            result = retriever.retrieve(request)
        evidence = list(result.evidence)
        if tool == ToolName.GET_REVIEWED_INCIDENTS:
            evidence = [item for item in evidence if item.kind == "reviewed_incident"]
        if not evidence:
            return ToolResult(
                tool=tool,
                status="error",
                summary="no eligible evidence matched the immutable cutoff",
                error_code="INSUFFICIENT_DATA",
            )
        return ToolResult(
            tool=tool,
            status="ok",
            summary=f"returned {len(evidence)} eligible evidence items",
            evidence=tuple(evidence),
            data={
                "source_ids": [item.source_id for item in evidence],
                "corpus_version": result.corpus_version,
            },
        )
