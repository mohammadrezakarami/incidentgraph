from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from pydantic import BaseModel

REQUIRED_FAULT_NAMES = (
    "downstream_latency",
    "pool_exhaustion",
    "dependency_errors",
    "cache_degradation",
    "deployment_regression",
    "resource_contention",
)
REQUIRED_FILES = {
    "MANIFEST.sha256",
    "changes.json",
    "logs.jsonl",
    "manifest.json",
    "metrics.json",
    "recovery.json",
    "topology.json",
    "traces.jsonl",
    "workload.json",
}
FORBIDDEN_AGENT_TERMS = (
    "expected_root_cause",
    "injected_fault_name",
    '"scenario"',
    '"accepted_mechanisms"',
)


class CaptureVerification(BaseModel):
    capture_count: int
    scenario_counts: dict[str, int]
    independent_fault_capture_count: int
    control_capture_count: int
    hash_manifests_valid: bool
    telemetry_signals_valid: bool
    trace_continuity_valid: bool
    evaluator_separation_valid: bool
    recovery_valid: bool


def verify_capture_suite(capture_root: Path, labels_path: Path) -> CaptureVerification:
    labels = _read_labels(labels_path)
    errors: list[str] = []
    counts = Counter(str(label["scenario"]) for label in labels)
    for scenario in REQUIRED_FAULT_NAMES:
        if counts[scenario] < 2:
            errors.append(f"{scenario} has fewer than two independent captures")

    hash_valid = True
    telemetry_valid = True
    trace_valid = True
    separation_valid = True
    recovery_valid = True
    for label in labels:
        capture_id = str(label["capture_id"])
        capture_dir = capture_root / capture_id
        if not capture_dir.is_dir():
            errors.append(f"missing capture directory: {capture_id}")
            continue
        files = {path.name for path in capture_dir.iterdir() if path.is_file()}
        if files != REQUIRED_FILES:
            errors.append(f"unexpected file set for {capture_id}: {sorted(files)}")
        if not _verify_hash_manifest(capture_dir):
            hash_valid = False
            errors.append(f"hash manifest failed for {capture_id}")
        if not _telemetry_signal_present(str(label["scenario"]), capture_dir):
            telemetry_valid = False
            errors.append(f"required telemetry signal missing for {capture_id}")
        if not _trace_continuity_present(capture_dir, str(label["scenario"])):
            trace_valid = False
            errors.append(f"cross-service trace continuity missing for {capture_id}")
        if not _agent_snapshot_is_separated(capture_dir):
            separation_valid = False
            errors.append(f"evaluator label leaked into {capture_id}")
        if not bool(label.get("recovery_verified")):
            recovery_valid = False
            errors.append(f"recovery failed for {capture_id}")
        if not bool(label.get("fault_effect_observed")):
            errors.append(f"effect check failed for {capture_id}")

    capture_dirs = {path.name for path in capture_root.iterdir() if path.is_dir()}
    labeled_dirs = {str(label["capture_id"]) for label in labels}
    if capture_dirs != labeled_dirs:
        errors.append("capture directories and evaluator label IDs differ")
    if capture_root.resolve() in labels_path.resolve().parents:
        separation_valid = False
        errors.append("evaluator labels are stored inside the agent-readable capture root")
    if errors:
        raise RuntimeError("; ".join(errors))

    independent_fault_count = sum(counts[scenario] for scenario in REQUIRED_FAULT_NAMES)
    return CaptureVerification(
        capture_count=len(labels),
        scenario_counts=dict(sorted(counts.items())),
        independent_fault_capture_count=independent_fault_count,
        control_capture_count=len(labels) - independent_fault_count,
        hash_manifests_valid=hash_valid,
        telemetry_signals_valid=telemetry_valid,
        trace_continuity_valid=trace_valid,
        evaluator_separation_valid=separation_valid,
        recovery_valid=recovery_valid,
    )


def _read_labels(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"missing evaluator labels: {path}")
    labels = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if not labels:
        raise RuntimeError("evaluator label file is empty")
    return labels


def _verify_hash_manifest(capture_dir: Path) -> bool:
    manifest_path = capture_dir / "MANIFEST.sha256"
    expected: dict[str, str] = {}
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", maxsplit=1)
        expected[name] = digest
    actual_files = {
        path.name
        for path in capture_dir.iterdir()
        if path.is_file() and path.name != manifest_path.name
    }
    if actual_files != set(expected):
        return False
    return all(
        hashlib.sha256((capture_dir / name).read_bytes()).hexdigest() == digest
        for name, digest in expected.items()
    )


def _series_values(metrics: dict[str, Any], template: str, **labels: str) -> list[float]:
    values: list[float] = []
    results = metrics[template]["data"].get("result", [])
    for series in results:
        series_labels = series.get("metric", {})
        if all(series_labels.get(key) == value for key, value in labels.items()):
            values.extend(float(point[1]) for point in series.get("values", []))
    return values


def _maximum(metrics: dict[str, Any], template: str, **labels: str) -> float:
    values = _series_values(metrics, template, **labels)
    return max(values, default=0)


def _minimum(metrics: dict[str, Any], template: str, **labels: str) -> float:
    values = _series_values(metrics, template, **labels)
    return min(values, default=1)


def _telemetry_signal_present(scenario: str, capture_dir: Path) -> bool:
    metrics = json.loads((capture_dir / "metrics.json").read_text(encoding="utf-8"))
    workload = json.loads((capture_dir / "workload.json").read_text(encoding="utf-8"))
    if scenario == "downstream_latency":
        return _maximum(metrics, "dependency_latency_p95", dependency="payments") >= 0.15
    if scenario == "pool_exhaustion":
        return (
            _maximum(metrics, "db_pool_in_use", service="checkout") == 4
            and workload["failure_count"] > 0
        )
    if scenario == "dependency_errors":
        return (
            _maximum(metrics, "dependency_outcomes", dependency="payments", outcome="error") > 0
            and workload["failure_count"] > 0
        )
    if scenario == "cache_degradation":
        return (
            _maximum(metrics, "cache_outcomes", service="payments", result="miss") > 0
            and workload["mean_latency_ms"] >= 25
        )
    if scenario == "deployment_regression":
        return _maximum(
            metrics,
            "deployment",
            service="checkout",
            version="v1.1.0-regressed",
        ) >= 1 and bool(json.loads((capture_dir / "changes.json").read_text(encoding="utf-8")))
    if scenario == "resource_contention":
        return (
            _maximum(metrics, "process_cpu", job="payments") >= 0.2
            and workload["p95_latency_ms"] >= 70
        )
    if scenario == "incomplete_telemetry":
        return _minimum(metrics, "scrape_health", job="payments") == 0
    if scenario == "ambiguous_two_cause":
        return float(workload["p95_latency_ms"]) >= 100 and int(workload["failure_count"]) > 0
    if scenario == "misleading_correlation":
        return workload["failure_count"] > 0 and _maximum(metrics, "process_cpu", job="gateway") > 0
    if scenario in {"healthy", "healthy_high_traffic"}:
        return int(workload["failure_count"]) == 0
    return False


def _trace_continuity_present(capture_dir: Path, scenario: str) -> bool:
    observations: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: {"services": set(), "trace_ids": set()}
    )
    for line in (capture_dir / "logs.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        request_id = row.get("request_id")
        service = row.get("service")
        trace_id = row.get("trace_id")
        if request_id and service and trace_id and row.get("method") == "POST":
            observations[request_id]["services"].add(service)
            observations[request_id]["trace_ids"].add(trace_id)
    expected_services = (
        {"gateway", "checkout"}
        if scenario == "pool_exhaustion"
        else {"gateway", "checkout", "payments"}
    )
    return any(
        observation["services"] == expected_services
        and len(observation["trace_ids"]) == 1
        for observation in observations.values()
    )


def _agent_snapshot_is_separated(capture_dir: Path) -> bool:
    for path in capture_dir.iterdir():
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if any(term in text for term in FORBIDDEN_AGENT_TERMS):
            return False
    return True
