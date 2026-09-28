from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest
from pydantic import SecretStr

from incidentgraph.config import Settings
from incidentgraph.investigation_tools import CaptureToolbox
from incidentgraph.investigator import ToolName, ToolRequest, ToolRuntimeContext
from incidentgraph.models import EvidenceItem


def settings() -> Settings:
    return Settings(
        environment="test",
        app_database_dsn=SecretStr("postgresql://app:test@localhost/app"),
        lab_database_dsn=SecretStr("postgresql://lab:test@localhost/lab"),
        neo4j_uri="bolt://localhost:7687",
        neo4j_password=SecretStr("test-only-password"),
        auth_tokens_json="{}",
    )


@pytest.fixture
def capture_root(tmp_path: Path) -> Path:
    capture = tmp_path / "cap-test-toolbox"
    capture.mkdir()
    (capture / "topology.json").write_text(
        json.dumps(
            {
                "dependencies": [
                    {"caller": "gateway", "callee": "checkout"},
                    {"caller": "checkout", "callee": "payments"},
                ]
            }
        )
    )

    def series(
        source: str, labels: dict[str, str], values: list[list[str | int]]
    ) -> dict[str, Any]:
        return {"metric": labels, "template_source": source, "values": values}

    (capture / "metrics.json").write_text(
        json.dumps(
            {
                "request_latency_p95": {
                    "data": {
                        "result": [
                            series(
                                "request_latency_p95",
                                {"service": "gateway", "route": "/checkout"},
                                [[1, "0.01"], [2, "0.2"]],
                            ),
                            series(
                                "request_latency_p95",
                                {"service": "payments", "route": "/pay"},
                                [[1, "0.03"]],
                            ),
                        ]
                    }
                },
                "request_rate": {
                    "data": {
                        "result": [
                            series(
                                "request_rate",
                                {"service": "gateway", "route": "/checkout"},
                                [[1, "5"]],
                            )
                        ]
                    }
                },
                "dependency_outcomes": {
                    "data": {
                        "result": [
                            series(
                                "dependency_outcomes",
                                {
                                    "service": "gateway",
                                    "dependency": "checkout",
                                    "outcome": "error",
                                },
                                [[1, "2"]],
                            )
                        ]
                    }
                },
                "db_pool_in_use": {
                    "data": {
                        "result": [
                            series(
                                "db_pool_in_use",
                                {"service": "checkout"},
                                [[1, "4"]],
                            )
                        ]
                    }
                },
                "db_pool_timeouts": {
                    "data": {
                        "result": [
                            series(
                                "db_pool_timeouts",
                                {"service": "checkout"},
                                [[1, "3"]],
                            )
                        ]
                    }
                },
                "cache_outcomes": {
                    "data": {
                        "result": [
                            series(
                                "cache_outcomes",
                                {"service": "payments", "result": "hit"},
                                [[1, "4"]],
                            )
                        ]
                    }
                },
                "process_cpu": {
                    "data": {"result": [series("process_cpu", {"job": "payments"}, [[1, "0.5"]])]}
                },
            }
        )
    )
    now = datetime(2026, 9, 28, 12, tzinfo=UTC)
    logs = [
        {
            "timestamp": now.isoformat(),
            "service": "gateway",
            "severity": "ERROR",
            "event": "request.failure",
            "trace_id": "a" * 32,
            "status_code": 503,
            "authorization": "must-not-leak",
        },
        {
            "timestamp": now.isoformat(),
            "service": "checkout",
            "severity": "INFO",
            "event": "request.ok",
            "trace_id": "b" * 32,
            "status_code": 200,
        },
    ]
    (capture / "logs.jsonl").write_text("\n".join(json.dumps(item) for item in logs) + "\n")
    (capture / "changes.json").write_text(
        json.dumps(
            [
                {
                    "service": "checkout",
                    "version": "v2",
                    "change_type": "deployment",
                    "observed_at": now.isoformat(),
                    "token": "must-not-leak",
                },
                {
                    "service": "unknown",
                    "version": "v1",
                    "observed_at": now.isoformat(),
                },
            ]
        )
    )
    return tmp_path


def context(snapshot_id: str = "cap-test-toolbox") -> ToolRuntimeContext:
    now = datetime(2026, 9, 28, 12, tzinfo=UTC)
    return ToolRuntimeContext(
        investigation_id=uuid4(),
        principal_id="viewer",
        authorized_service_ids=("svc-gateway", "svc-checkout", "svc-payments"),
        environment="lab",
        window_start=now - timedelta(minutes=1),
        window_end=now + timedelta(minutes=1),
        observation_cutoff=now,
        snapshot_id=snapshot_id,
    )


def request(tool: ToolName, arguments: dict[str, Any]) -> ToolRequest:
    return ToolRequest(tool=tool, arguments=arguments, reason="Exercise a bounded read adapter.")


async def test_snapshot_validation_and_dispatch_errors(capture_root: Path) -> None:
    toolbox = CaptureToolbox(settings(), capture_root)
    now = context().observation_cutoff
    invalid = await toolbox.execute(
        request(
            ToolName.GET_METRICS,
            {
                "service_id": "svc-gateway",
                "template": "request_latency",
                "window_start": now - timedelta(minutes=1),
                "window_end": now,
                "resolution_seconds": 1,
            },
        ),
        context("../escape"),
    )
    assert invalid.error_code == "INVALID_ARGUMENT"

    missing = await toolbox.execute(
        request(
            ToolName.GET_METRICS,
            {
                "service_id": "svc-gateway",
                "template": "request_latency",
                "window_start": now - timedelta(minutes=1),
                "window_end": now,
                "resolution_seconds": 1,
            },
        ),
        context("cap-test-missing"),
    )
    assert missing.error_code == "NOT_FOUND"

    malformed = await toolbox.execute(
        request(ToolName.GET_METRICS, {"service_id": "svc-gateway"}), context()
    )
    assert malformed.error_code == "INVALID_ARGUMENT"


@pytest.mark.parametrize(
    ("service_id", "template", "sources"),
    [
        ("svc-gateway", "request_latency", {"request_latency_p95", "request_rate"}),
        ("svc-gateway", "error_rate", {"dependency_outcomes"}),
        ("svc-checkout", "db_pool", {"db_pool_in_use", "db_pool_timeouts"}),
        ("svc-payments", "cache_outcomes", {"cache_outcomes"}),
        ("svc-payments", "cpu_time", {"process_cpu"}),
    ],
)
async def test_metric_templates_return_bounded_summaries(
    capture_root: Path, service_id: str, template: str, sources: set[str]
) -> None:
    runtime = context()
    result = await CaptureToolbox(settings(), capture_root).execute(
        request(
            ToolName.GET_METRICS,
            {
                "service_id": service_id,
                "template": template,
                "window_start": runtime.window_start,
                "window_end": runtime.window_end,
                "resolution_seconds": 1,
            },
        ),
        runtime,
    )
    assert result.status == "ok"
    assert {item["template_source"] for item in result.data["series_summaries"]} == sources
    assert result.data["point_count"] >= 1
    assert result.evidence[0].content and "must-not-leak" not in result.evidence[0].content


async def test_metrics_distinguish_absent_template_and_no_matching_series(
    capture_root: Path,
) -> None:
    runtime = context()
    capture = capture_root / "cap-test-toolbox"
    raw = json.loads((capture / "metrics.json").read_text())
    raw.pop("process_cpu")
    (capture / "metrics.json").write_text(json.dumps(raw))
    toolbox = CaptureToolbox(settings(), capture_root)
    absent = await toolbox.execute(
        request(
            ToolName.GET_METRICS,
            {
                "service_id": "svc-payments",
                "template": "cpu_time",
                "window_start": runtime.window_start,
                "window_end": runtime.window_end,
                "resolution_seconds": 1,
            },
        ),
        runtime,
    )
    unmatched = await toolbox.execute(
        request(
            ToolName.GET_METRICS,
            {
                "service_id": "svc-payments",
                "template": "error_rate",
                "window_start": runtime.window_start,
                "window_end": runtime.window_end,
                "resolution_seconds": 1,
            },
        ),
        runtime,
    )
    assert absent.error_code == unmatched.error_code == "INSUFFICIENT_DATA"
    assert "absent" in absent.summary
    assert "matched" in unmatched.summary


async def test_logs_apply_all_filters_bounds_and_redaction(capture_root: Path) -> None:
    runtime = context()
    toolbox = CaptureToolbox(settings(), capture_root)
    matched = await toolbox.execute(
        request(
            ToolName.SEARCH_LOGS,
            {
                "service_ids": ["svc-gateway"],
                "window_start": runtime.window_start,
                "window_end": runtime.window_end,
                "severity": "ERROR",
                "event": "request.failure",
                "trace_id": "a" * 32,
                "limit": 1,
            },
        ),
        runtime,
    )
    assert matched.status == "ok", matched.summary
    assert matched.data == {
        "event_count": 1,
        "services": {"gateway": 1},
        "severities": {"ERROR": 1},
        "event_types": {"request.failure": 1},
        "status_codes": {"503": 1},
        "trace_ids": ["a" * 32],
    }
    assert "[REDACTED]" in (matched.evidence[0].content or "")
    assert "must-not-leak" not in (matched.evidence[0].content or "")

    missing = await toolbox.execute(
        request(
            ToolName.SEARCH_LOGS,
            {
                "service_ids": ["svc-payments"],
                "window_start": runtime.window_start,
                "window_end": runtime.window_end,
                "event": "does.not.exist",
                "limit": 10,
            },
        ),
        runtime,
    )
    assert missing.error_code == "INSUFFICIENT_DATA"


async def test_changes_and_captured_dependencies_are_authorization_scoped(
    capture_root: Path,
) -> None:
    runtime = context()
    toolbox = CaptureToolbox(settings(), capture_root)
    changes = await toolbox.execute(
        request(
            ToolName.GET_RECENT_CHANGES,
            {
                "service_ids": ["svc-checkout"],
                "window_start": runtime.window_start,
                "window_end": runtime.window_end,
            },
        ),
        runtime,
    )
    assert changes.status == "ok"
    assert changes.data["changes"] == [
        {
            "service": "checkout",
            "version": "v2",
            "change_type": "deployment",
            "observed_at": runtime.observation_cutoff.isoformat(),
        }
    ]
    assert "must-not-leak" not in (changes.evidence[0].content or "")

    no_changes = await toolbox.execute(
        request(
            ToolName.GET_RECENT_CHANGES,
            {
                "service_ids": ["svc-payments"],
                "window_start": runtime.window_start,
                "window_end": runtime.window_end,
            },
        ),
        runtime,
    )
    assert no_changes.error_code == "INSUFFICIENT_DATA"

    dependencies = await toolbox.execute(
        request(
            ToolName.GET_DEPENDENCIES,
            {
                "service_id": "svc-payments",
                "direction": "inbound",
                "depth": 2,
                "observation_time": runtime.observation_cutoff,
            },
        ),
        runtime,
    )
    assert dependencies.status == "ok"
    assert dependencies.data["path_count"] == 2


async def test_resolve_and_service_context_enforce_topology_and_authorization(
    capture_root: Path,
) -> None:
    toolbox = CaptureToolbox(settings(), capture_root)
    runtime = context()
    resolved = await toolbox.execute(
        request(ToolName.RESOLVE_SERVICE, {"name": "gateway", "environment": "lab"}),
        runtime,
    )
    assert resolved.data["service_id"] == "svc-gateway"

    missing = await toolbox.execute(
        request(ToolName.RESOLVE_SERVICE, {"name": "missing", "environment": "lab"}),
        runtime,
    )
    assert missing.error_code == "NOT_FOUND"

    unauthorized_runtime = runtime.model_copy(update={"authorized_service_ids": ("svc-gateway",)})
    unauthorized = await toolbox.execute(
        request(ToolName.RESOLVE_SERVICE, {"name": "payments", "environment": "lab"}),
        unauthorized_runtime,
    )
    assert unauthorized.error_code == "UNAUTHORIZED"

    service = await toolbox.execute(
        request(
            ToolName.GET_SERVICE_CONTEXT,
            {
                "service_id": "svc-gateway",
                "observation_time": runtime.observation_cutoff,
            },
        ),
        runtime,
    )
    assert service.status == "ok", service.summary
    assert service.evidence[0].kind == "topology"

    absent = await toolbox.execute(
        request(
            ToolName.GET_SERVICE_CONTEXT,
            {
                "service_id": "svc-unknown",
                "observation_time": runtime.observation_cutoff,
            },
        ),
        runtime,
    )
    assert absent.error_code == "NOT_FOUND"


def retrieved_evidence(kind: str, source: str) -> EvidenceItem:
    now = datetime(2026, 9, 28, 12, tzinfo=UTC)
    return EvidenceItem(
        evidence_id=uuid5(NAMESPACE_URL, source),
        kind=kind,  # type: ignore[arg-type]
        source_id=source,
        source_version="1",
        service_ids=["svc-gateway"],
        environment="lab",
        observed_at=now,
        collected_at=now,
        content_hash="d" * 64,
        freshness_status="fresh",
        provenance_reference=f"test://{source}",
    )


async def test_retrieval_adapter_filters_reviewed_incidents(
    capture_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    docs = retrieved_evidence("document", "runbook")
    incident = retrieved_evidence("reviewed_incident", "incident-1")

    class FakeRetriever:
        def __init__(self, configured: Settings) -> None:
            del configured

        def __enter__(self) -> FakeRetriever:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def retrieve(self, value: Any) -> Any:
            assert value.authorized_service_ids == context().authorized_service_ids
            return SimpleNamespace(evidence=(docs, incident), corpus_version="corpus-v1")

    monkeypatch.setattr("incidentgraph.investigation_tools.Neo4jRetriever", FakeRetriever)
    runtime = context()
    arguments = {
        "query": "Find grounded operational guidance",
        "service_ids": ["svc-gateway"],
        "cutoff": runtime.observation_cutoff,
        "variant": "graph",
    }
    toolbox = CaptureToolbox(settings(), capture_root)
    runbooks = await toolbox.execute(request(ToolName.RETRIEVE_RUNBOOKS, arguments), runtime)
    reviewed = await toolbox.execute(request(ToolName.GET_REVIEWED_INCIDENTS, arguments), runtime)
    assert [item.source_id for item in runbooks.evidence] == ["runbook", "incident-1"]
    assert [item.source_id for item in reviewed.evidence] == ["incident-1"]


async def test_unexpected_source_failure_is_fail_closed(
    capture_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    toolbox = CaptureToolbox(settings(), capture_root)

    def explode(*_: Any) -> Any:
        raise RuntimeError("secret backend detail")

    monkeypatch.setattr(toolbox, "_metrics", explode)
    runtime = context()
    result = await toolbox.execute(
        request(
            ToolName.GET_METRICS,
            {
                "service_id": "svc-gateway",
                "template": "request_latency",
                "window_start": runtime.window_start,
                "window_end": runtime.window_end,
                "resolution_seconds": 1,
            },
        ),
        runtime,
    )
    assert result.error_code == "UNAVAILABLE"
    assert "RuntimeError" in result.summary
    assert "secret backend detail" not in result.summary
