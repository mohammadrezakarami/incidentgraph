from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from incidentgraph.lab_cli import (
    LabOperatorSettings,
    WorkloadResult,
    apply_capture_telemetry_policy,
    run_workload,
    scenario_controls,
    write_capture,
)
from incidentgraph.lab_runtime import FaultCommand, FaultState, verify_control_token


def operator_settings(tmp_path: Path) -> LabOperatorSettings:
    return LabOperatorSettings(
        environment="test",
        app_database_dsn="postgresql://app:test@localhost/app",
        lab_database_dsn="postgresql://lab:test@localhost/lab",
        neo4j_uri="bolt://localhost:7687",
        neo4j_password="test-only-password",
        lab_control_token="control-token-with-at-least-32-characters",
        lab_log_dir=tmp_path / "runtime" / "logs",
        lab_trace_dir=tmp_path / "runtime" / "traces",
        lab_capture_dir=tmp_path / "captures",
        lab_evaluator_labels=tmp_path / "evaluator" / "labels.jsonl",
    )


def workload(now: datetime) -> WorkloadResult:
    return WorkloadResult(
        started_at=now,
        ended_at=now,
        duration_seconds=1,
        rate_per_second=1,
        concurrency=1,
        seed=1,
        request_count=1,
        success_count=1,
        failure_count=0,
        status_counts={"200": 1},
        mean_latency_ms=10,
        p95_latency_ms=10,
        max_latency_ms=10,
    )


def test_fault_contract_requires_mechanism_parameters() -> None:
    with pytest.raises(ValidationError, match="delay_ms"):
        FaultCommand(kind="latency", duration_seconds=5)


def test_fault_state_expires_without_an_explicit_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = {"value": 100.0}
    monkeypatch.setattr("incidentgraph.lab_runtime.time.monotonic", lambda: clock["value"])
    state = FaultState(max_duration_seconds=30)
    state.apply(FaultCommand(kind="latency", duration_seconds=2, delay_ms=10))

    assert state.current() is not None
    clock["value"] = 103.0
    assert state.current() is None


def test_control_tokens_use_hash_comparison(tmp_path: Path) -> None:
    settings = operator_settings(tmp_path)

    assert verify_control_token(
        "control-token-with-at-least-32-characters",
        settings.lab_control_token,
    )
    assert not verify_control_token("wrong-token", settings.lab_control_token)


def test_all_required_faults_have_bounded_controls() -> None:
    scenarios = (
        "downstream_latency",
        "pool_exhaustion",
        "dependency_errors",
        "cache_degradation",
        "deployment_regression",
        "resource_contention",
    )
    for scenario in scenarios:
        controls = scenario_controls(scenario, seed=7, duration_seconds=6)  # type: ignore[arg-type]
        assert controls
        assert all(command.duration_seconds <= 30 for _, command in controls)


@pytest.mark.asyncio
async def test_workload_rejects_unbounded_parameters(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="duration_seconds"):
        await run_workload(
            operator_settings(tmp_path),
            duration_seconds=31,
            rate_per_second=1,
            concurrency=1,
            seed=1,
            prefix="bounded",
        )


def test_capture_keeps_evaluator_label_outside_agent_snapshot(tmp_path: Path) -> None:
    settings = operator_settings(tmp_path)
    now = datetime.now(UTC)
    capture_dir = write_capture(
        settings,
        capture_id="cap-test-0001",
        scenario="healthy",
        seed=1,
        observation_start=now,
        observation_cutoff=now,
        workload=workload(now),
        recovery=workload(now),
        metrics={},
        controls=[],
    )

    manifest = json.loads((capture_dir / "manifest.json").read_text(encoding="utf-8"))
    labels = json.loads(settings.lab_evaluator_labels.read_text(encoding="utf-8"))
    assert "scenario" not in manifest
    assert "accepted_mechanisms" not in manifest
    assert labels["scenario"] == "healthy"
    assert settings.lab_evaluator_labels.parent not in capture_dir.parents


def test_incomplete_telemetry_is_materialized_in_the_capture() -> None:
    metrics = {
        "scrape_health": {
            "data": {
                "result": [
                    {"metric": {"job": "checkout", "instance": "checkout:8080"}},
                    {"metric": {"job": "payments", "instance": "payments:8080"}},
                ]
            }
        },
        "dependency_outcomes": {
            "data": {
                "result": [
                    {
                        "metric": {
                            "service": "checkout",
                            "dependency": "payments",
                            "outcome": "success",
                        }
                    }
                ]
            }
        },
    }
    logs = [{"service": "checkout"}, {"service": "payments"}]
    traces = [
        {"attributes": {"service.name": "checkout"}},
        {"attributes": {"service.name": "payments"}},
    ]

    captured_metrics, captured_logs, captured_traces, gaps = apply_capture_telemetry_policy(
        "incomplete_telemetry", metrics, logs, traces
    )

    scrape_rows = captured_metrics["scrape_health"]["data"]["result"]
    dependency_rows = captured_metrics["dependency_outcomes"]["data"]["result"]
    assert [row["metric"]["job"] for row in scrape_rows] == ["checkout"]
    assert dependency_rows == metrics["dependency_outcomes"]["data"]["result"]
    assert captured_logs == [{"service": "checkout"}]
    assert captured_traces == [{"attributes": {"service.name": "checkout"}}]
    assert gaps
    assert len(metrics["scrape_health"]["data"]["result"]) == 2
