from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import random
import statistics
import time
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field, SecretStr

from incidentgraph.capture_verification import verify_capture_suite
from incidentgraph.config import Settings
from incidentgraph.lab_runtime import FaultCommand
from incidentgraph.persistence import Database

ROOT = Path(__file__).resolve().parents[2]
LAB_MIGRATION = ROOT / "ops" / "migrations" / "002_lab.sql"

ScenarioName = Literal[
    "downstream_latency",
    "pool_exhaustion",
    "dependency_errors",
    "cache_degradation",
    "deployment_regression",
    "resource_contention",
    "healthy",
    "healthy_high_traffic",
    "misleading_correlation",
    "incomplete_telemetry",
    "ambiguous_two_cause",
]

REQUIRED_FAULTS: tuple[ScenarioName, ...] = (
    "downstream_latency",
    "pool_exhaustion",
    "dependency_errors",
    "cache_degradation",
    "deployment_regression",
    "resource_contention",
)
CONTROL_SCENARIOS: tuple[ScenarioName, ...] = (
    "healthy",
    "healthy_high_traffic",
    "misleading_correlation",
    "incomplete_telemetry",
    "ambiguous_two_cause",
)


class LabOperatorSettings(Settings):
    lab_control_token: SecretStr = Field(min_length=32)
    lab_gateway_url: str = "http://127.0.0.1:58080"
    lab_checkout_url: str = "http://127.0.0.1:58081"
    lab_payments_url: str = "http://127.0.0.1:58082"
    prometheus_url: str = "http://127.0.0.1:59090"
    lab_redis_url: str = "redis://127.0.0.1:56379/0"
    lab_log_dir: Path = Path("data/runtime/lab-logs")
    lab_trace_dir: Path = Path("data/runtime/lab-traces")
    lab_capture_dir: Path = Path("data/captures")
    lab_evaluator_labels: Path = Path("data/evaluator/phase2-labels.jsonl")


class WorkloadResult(BaseModel):
    started_at: datetime
    ended_at: datetime
    duration_seconds: float
    rate_per_second: float
    concurrency: int
    seed: int
    request_count: int
    success_count: int
    failure_count: int
    status_counts: dict[str, int]
    mean_latency_ms: float
    p95_latency_ms: float
    max_latency_ms: float


async def migrate_lab(settings: LabOperatorSettings) -> None:
    database = Database(settings.lab_database_dsn.get_secret_value())
    await database.open()
    try:
        await database.apply_migration(LAB_MIGRATION)
    finally:
        await database.close()


async def wait_ready(settings: LabOperatorSettings, timeout_seconds: float = 45) -> None:
    urls = (
        settings.lab_gateway_url,
        settings.lab_checkout_url,
        settings.lab_payments_url,
    )
    deadline = time.monotonic() + timeout_seconds
    async with httpx.AsyncClient(timeout=2) as client:
        while time.monotonic() < deadline:
            results = await asyncio.gather(
                *(client.get(f"{url}/health/ready") for url in urls),
                return_exceptions=True,
            )
            if all(
                isinstance(result, httpx.Response) and result.status_code == 200
                for result in results
            ):
                return
            await asyncio.sleep(1)
    raise TimeoutError("lab services did not become ready within the bounded wait")


async def run_workload(
    settings: LabOperatorSettings,
    *,
    duration_seconds: float,
    rate_per_second: float,
    concurrency: int,
    seed: int,
    prefix: str,
) -> WorkloadResult:
    if not 0.5 <= duration_seconds <= 30:
        raise ValueError("duration_seconds must be between 0.5 and 30")
    if not 0.5 <= rate_per_second <= 30:
        raise ValueError("rate_per_second must be between 0.5 and 30")
    if not 1 <= concurrency <= 20:
        raise ValueError("concurrency must be between 1 and 20")
    request_count = min(600, max(1, math.ceil(duration_seconds * rate_per_second)))
    semaphore = asyncio.Semaphore(concurrency)
    started_at = datetime.now(UTC)
    started_monotonic = time.monotonic()
    statuses: list[int] = []
    latencies: list[float] = []
    randomizer = random.Random(seed)  # noqa: S311 - reproducible synthetic workload, not security.

    async with httpx.AsyncClient(timeout=3) as client:

        async def send(index: int) -> None:
            target_time = started_monotonic + index / rate_per_second
            await asyncio.sleep(max(0, target_time - time.monotonic()))
            async with semaphore:
                request_started = time.perf_counter()
                order = {
                    "order_id": f"ord-{prefix}-{index}",
                    "amount_cents": randomizer.randint(100, 10_000),
                    "payment_token": f"tok_test_{index % 8}",
                }
                try:
                    response = await client.post(
                        f"{settings.lab_gateway_url}/checkout",
                        headers={"X-Request-ID": f"req-{prefix}-{index}"},
                        json=order,
                    )
                    statuses.append(response.status_code)
                except httpx.HTTPError:
                    statuses.append(599)
                latencies.append((time.perf_counter() - request_started) * 1_000)

        await asyncio.gather(*(send(index) for index in range(request_count)))

    ended_at = datetime.now(UTC)
    sorted_latencies = sorted(latencies)
    p95_index = min(len(sorted_latencies) - 1, math.ceil(len(sorted_latencies) * 0.95) - 1)
    status_counts: dict[str, int] = {}
    for status_code in statuses:
        key = str(status_code)
        status_counts[key] = status_counts.get(key, 0) + 1
    successes = sum(1 for status_code in statuses if 200 <= status_code < 300)
    return WorkloadResult(
        started_at=started_at,
        ended_at=ended_at,
        duration_seconds=round((ended_at - started_at).total_seconds(), 3),
        rate_per_second=rate_per_second,
        concurrency=concurrency,
        seed=seed,
        request_count=request_count,
        success_count=successes,
        failure_count=len(statuses) - successes,
        status_counts=status_counts,
        mean_latency_ms=round(statistics.fmean(latencies), 3),
        p95_latency_ms=round(sorted_latencies[p95_index], 3),
        max_latency_ms=round(max(latencies), 3),
    )


def scenario_controls(
    scenario: ScenarioName,
    seed: int,
    duration_seconds: int,
) -> list[tuple[Literal["gateway", "checkout", "payments"], FaultCommand]]:
    bounded_duration = min(30, max(5, duration_seconds + 5))
    commands: dict[
        ScenarioName, list[tuple[Literal["gateway", "checkout", "payments"], FaultCommand]]
    ] = {
        "downstream_latency": [
            (
                "payments",
                FaultCommand(
                    kind="latency", duration_seconds=bounded_duration, seed=seed, delay_ms=220
                ),
            )
        ],
        "pool_exhaustion": [
            (
                "checkout",
                FaultCommand(
                    kind="pool_exhaustion",
                    duration_seconds=bounded_duration,
                    seed=seed,
                    hold_connections=4,
                ),
            )
        ],
        "dependency_errors": [
            (
                "payments",
                FaultCommand(
                    kind="dependency_errors",
                    duration_seconds=bounded_duration,
                    seed=seed,
                    error_rate=0.5,
                ),
            )
        ],
        "cache_degradation": [
            (
                "payments",
                FaultCommand(
                    kind="cache_degradation",
                    duration_seconds=bounded_duration,
                    seed=seed,
                ),
            )
        ],
        "deployment_regression": [
            (
                "checkout",
                FaultCommand(
                    kind="deployment_regression",
                    duration_seconds=bounded_duration,
                    seed=seed,
                    delay_ms=90,
                    error_rate=0.3,
                    deployment_version="v1.1.0-regressed",
                ),
            )
        ],
        "resource_contention": [
            (
                "payments",
                FaultCommand(
                    kind="resource_contention",
                    duration_seconds=bounded_duration,
                    seed=seed,
                    cpu_ms=90,
                ),
            )
        ],
        "healthy": [],
        "healthy_high_traffic": [],
        "misleading_correlation": [
            (
                "gateway",
                FaultCommand(
                    kind="resource_contention",
                    duration_seconds=bounded_duration,
                    seed=seed,
                    cpu_ms=8,
                ),
            ),
            (
                "payments",
                FaultCommand(
                    kind="dependency_errors",
                    duration_seconds=bounded_duration,
                    seed=seed,
                    error_rate=0.45,
                ),
            ),
        ],
        "incomplete_telemetry": [
            (
                "payments",
                FaultCommand(
                    kind="metrics_disabled",
                    duration_seconds=bounded_duration,
                    seed=seed,
                ),
            )
        ],
        "ambiguous_two_cause": [
            (
                "checkout",
                FaultCommand(
                    kind="deployment_regression",
                    duration_seconds=bounded_duration,
                    seed=seed,
                    delay_ms=65,
                    error_rate=0.2,
                    deployment_version="v1.1.0-regressed",
                ),
            ),
            (
                "payments",
                FaultCommand(
                    kind="latency",
                    duration_seconds=bounded_duration,
                    seed=seed,
                    delay_ms=140,
                ),
            ),
        ],
    }
    return commands[scenario]


def _service_url(settings: LabOperatorSettings, service: str) -> str:
    return {
        "gateway": settings.lab_gateway_url,
        "checkout": settings.lab_checkout_url,
        "payments": settings.lab_payments_url,
    }[service]


async def reset_faults(settings: LabOperatorSettings) -> None:
    headers = {"X-Lab-Control-Token": settings.lab_control_token.get_secret_value()}
    async with httpx.AsyncClient(timeout=3) as client:
        await asyncio.gather(
            *(
                client.delete(f"{url}/__control/fault", headers=headers)
                for url in (
                    settings.lab_gateway_url,
                    settings.lab_checkout_url,
                    settings.lab_payments_url,
                )
            )
        )


async def apply_controls(
    settings: LabOperatorSettings,
    controls: Sequence[tuple[str, FaultCommand]],
) -> None:
    headers = {"X-Lab-Control-Token": settings.lab_control_token.get_secret_value()}
    async with httpx.AsyncClient(timeout=3) as client:
        for service, command in controls:
            response = await client.post(
                f"{_service_url(settings, service)}/__control/fault",
                headers=headers,
                json=command.model_dump(),
            )
            response.raise_for_status()


METRIC_TEMPLATES: dict[str, str] = {
    "request_rate": (
        "sum by (service, route, status_class) "
        '(rate(lab_http_requests_total{route!="/metrics"}[5s]))'
    ),
    "request_latency_p95": (
        "histogram_quantile(0.95, sum by (le, service, route) "
        '(rate(lab_http_request_duration_seconds_bucket{route!="/metrics"}[5s])))'
    ),
    "dependency_outcomes": (
        "sum by (service, dependency, outcome) (rate(lab_outbound_requests_total[5s]))"
    ),
    "dependency_latency_p95": (
        "histogram_quantile(0.95, sum by (le, service, dependency) "
        "(rate(lab_outbound_request_duration_seconds_bucket[5s])))"
    ),
    "db_pool_in_use": "lab_db_pool_in_use",
    "db_pool_timeouts": "sum by (service) (increase(lab_db_pool_timeouts_total[10s]))",
    "cache_outcomes": "sum by (service, result) (rate(lab_cache_requests_total[5s]))",
    "process_cpu": "sum by (job) (rate(process_cpu_seconds_total[5s]))",
    "deployment": "lab_deployment_info",
    "scrape_health": 'up{job=~"gateway|checkout|payments"}',
}


async def query_metrics(
    settings: LabOperatorSettings,
    start: datetime,
    end: datetime,
) -> dict[str, Any]:
    results: dict[str, Any] = {}
    async with httpx.AsyncClient(timeout=5) as client:
        for template_id, query in METRIC_TEMPLATES.items():
            response = await client.get(
                f"{settings.prometheus_url}/api/v1/query_range",
                params={
                    "query": query,
                    "start": start.timestamp(),
                    "end": end.timestamp(),
                    "step": "1s",
                },
            )
            response.raise_for_status()
            body = response.json()
            results[template_id] = {
                "template_id": template_id,
                "parameters": {
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "step_seconds": 1,
                },
                "status": body.get("status"),
                "data": body.get("data", {}),
            }
    return results


def _read_json_lines(
    path: Path, start: datetime, end: datetime, time_field: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            timestamp_value = row.get(time_field)
            if not timestamp_value:
                continue
            observed = datetime.fromisoformat(timestamp_value)
            if start <= observed <= end:
                rows.append(row)
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
    return rows


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(len(ordered) * percentile) - 1))
    return ordered[index]


def validate_effect(scenario: ScenarioName, workload: WorkloadResult) -> bool:
    if scenario == "downstream_latency":
        return workload.p95_latency_ms >= 150
    if scenario in {"pool_exhaustion", "dependency_errors", "deployment_regression"}:
        return workload.failure_count > 0
    if scenario == "cache_degradation":
        return workload.mean_latency_ms >= 25
    if scenario == "resource_contention":
        return workload.p95_latency_ms >= 70
    if scenario in {"misleading_correlation", "ambiguous_two_cause"}:
        return workload.failure_count > 0 or workload.p95_latency_ms >= 100
    return True


def write_capture(
    settings: LabOperatorSettings,
    *,
    capture_id: str,
    scenario: ScenarioName,
    seed: int,
    observation_start: datetime,
    observation_cutoff: datetime,
    workload: WorkloadResult,
    recovery: WorkloadResult,
    metrics: dict[str, Any],
    controls: Sequence[tuple[str, FaultCommand]],
) -> Path:
    capture_dir = settings.lab_capture_dir / capture_id
    if capture_dir.exists():
        raise FileExistsError(f"capture already exists: {capture_dir}")
    capture_dir.mkdir(parents=True)

    logs: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    for service in ("gateway", "checkout", "payments"):
        logs.extend(
            _read_json_lines(
                settings.lab_log_dir / f"{service}.jsonl",
                observation_start,
                observation_cutoff,
                "timestamp",
            )
        )
        traces.extend(
            _read_json_lines(
                settings.lab_trace_dir / f"{service}.jsonl",
                observation_start,
                observation_cutoff,
                "start_time",
            )
        )

    changes: list[dict[str, Any]] = []
    for service, command in controls:
        if command.kind == "deployment_regression":
            changes.append(
                {
                    "service": service,
                    "version": command.deployment_version,
                    "observed_at": observation_start.isoformat(),
                    "source": "lab-deployment-controller",
                }
            )

    files: dict[str, Any] = {
        "manifest.json": {
            "capture_id": capture_id,
            "mode": "live_capture",
            "environment": "lab",
            "observation_start": observation_start.isoformat(),
            "observation_cutoff": observation_cutoff.isoformat(),
            "services": ["gateway", "checkout", "payments"],
            "provenance_category": "independent_lab_capture",
            "limitations": [
                "laboratory data, not production evidence",
                "Phase 2 capture predates the curated Phase 3 corpus",
            ],
        },
        "workload.json": workload.model_dump(mode="json"),
        "recovery.json": recovery.model_dump(mode="json"),
        "metrics.json": metrics,
        "topology.json": {
            "services": ["gateway", "checkout", "payments"],
            "dependencies": [
                {"caller": "gateway", "callee": "checkout"},
                {"caller": "checkout", "callee": "payments"},
                {"caller": "checkout", "resource": "lab-postgresql"},
                {"caller": "payments", "resource": "lab-postgresql"},
                {"caller": "payments", "resource": "lab-redis"},
            ],
        },
        "changes.json": changes,
    }
    for name, payload in files.items():
        (capture_dir / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
    (capture_dir / "logs.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True, default=str) + "\n" for row in logs),
        encoding="utf-8",
    )
    (capture_dir / "traces.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True, default=str) + "\n" for row in traces),
        encoding="utf-8",
    )

    hash_lines = []
    for path in sorted(capture_dir.iterdir()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        hash_lines.append(f"{digest}  {path.name}")
    (capture_dir / "MANIFEST.sha256").write_text("\n".join(hash_lines) + "\n", encoding="utf-8")

    effect_observed = validate_effect(scenario, workload)
    settings.lab_evaluator_labels.parent.mkdir(parents=True, exist_ok=True)
    label = {
        "capture_id": capture_id,
        "scenario": scenario,
        "seed": seed,
        "answerability": "insufficient_observation"
        if scenario == "incomplete_telemetry"
        else "answerable",
        "accepted_components": _accepted_components(scenario),
        "accepted_mechanisms": _accepted_mechanisms(scenario),
        "setup": [
            {"service": service, **command.model_dump(mode="json")} for service, command in controls
        ],
        "observation_start": observation_start.isoformat(),
        "observation_cutoff": observation_cutoff.isoformat(),
        "workload": workload.model_dump(mode="json"),
        "bounded_impact": {
            "request_count": workload.request_count,
            "failure_count": workload.failure_count,
            "p95_latency_ms": workload.p95_latency_ms,
        },
        "fault_effect_observed": effect_observed,
        "recovery_verified": recovery.success_count == recovery.request_count,
        "provenance_category": "independent_lab_capture",
    }
    with settings.lab_evaluator_labels.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(label, sort_keys=True, default=str) + "\n")
    if not effect_observed:
        raise RuntimeError(f"scenario {scenario} did not meet its measured effect check")
    if recovery.success_count != recovery.request_count:
        raise RuntimeError(f"scenario {scenario} did not recover cleanly")
    return capture_dir


def _accepted_components(scenario: ScenarioName) -> list[str]:
    mapping: dict[ScenarioName, list[str]] = {
        "downstream_latency": ["payments"],
        "pool_exhaustion": ["checkout", "lab-postgresql"],
        "dependency_errors": ["payments"],
        "cache_degradation": ["payments", "lab-redis"],
        "deployment_regression": ["checkout"],
        "resource_contention": ["payments"],
        "healthy": [],
        "healthy_high_traffic": [],
        "misleading_correlation": ["payments"],
        "incomplete_telemetry": [],
        "ambiguous_two_cause": ["checkout", "payments"],
    }
    return mapping[scenario]


def _accepted_mechanisms(scenario: ScenarioName) -> list[str]:
    mapping: dict[ScenarioName, list[str]] = {
        "downstream_latency": ["downstream_latency"],
        "pool_exhaustion": ["database_pool_exhaustion"],
        "dependency_errors": ["dependency_errors"],
        "cache_degradation": ["cache_degradation"],
        "deployment_regression": ["deployment_regression"],
        "resource_contention": ["cpu_contention"],
        "healthy": ["healthy"],
        "healthy_high_traffic": ["healthy_high_traffic"],
        "misleading_correlation": ["dependency_errors"],
        "incomplete_telemetry": ["insufficient_observation"],
        "ambiguous_two_cause": ["deployment_regression", "downstream_latency"],
    }
    return mapping[scenario]


async def run_scenario(
    settings: LabOperatorSettings,
    *,
    scenario: ScenarioName,
    seed: int,
    duration_seconds: int,
    rate_per_second: float,
    concurrency: int,
) -> Path:
    await wait_ready(settings)
    await reset_faults(settings)
    warm_prefix = f"warm-{seed}-{uuid4().hex[:6]}"
    await run_workload(
        settings,
        duration_seconds=1,
        rate_per_second=5,
        concurrency=2,
        seed=seed,
        prefix=warm_prefix,
    )
    controls = scenario_controls(scenario, seed, duration_seconds)
    await apply_controls(settings, controls)
    await asyncio.sleep(1.5)
    observation_start = datetime.now(UTC)
    capture_id = f"cap-{observation_start.strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:10]}"
    effective_rate = 18 if scenario == "healthy_high_traffic" else rate_per_second
    workload = await run_workload(
        settings,
        duration_seconds=duration_seconds,
        rate_per_second=effective_rate,
        concurrency=concurrency,
        seed=seed,
        prefix=capture_id.removeprefix("cap-"),
    )
    await asyncio.sleep(2)
    observation_cutoff = datetime.now(UTC)
    metrics = await query_metrics(
        settings,
        observation_start - timedelta(seconds=1),
        observation_cutoff,
    )
    await reset_faults(settings)
    await asyncio.sleep(0.5)
    recovery = await run_workload(
        settings,
        duration_seconds=1,
        rate_per_second=3,
        concurrency=2,
        seed=seed + 10_000,
        prefix=f"recovery-{uuid4().hex[:8]}",
    )
    return write_capture(
        settings,
        capture_id=capture_id,
        scenario=scenario,
        seed=seed,
        observation_start=observation_start,
        observation_cutoff=observation_cutoff,
        workload=workload,
        recovery=recovery,
        metrics=metrics,
        controls=controls,
    )


async def capture_suite(
    settings: LabOperatorSettings,
    duration_seconds: int,
    rate_per_second: float,
    concurrency: int,
) -> list[Path]:
    captures: list[Path] = []
    for scenario_index, scenario in enumerate(REQUIRED_FAULTS):
        for independent_run in range(2):
            seed = 2_000 + scenario_index * 100 + independent_run
            capture = await run_scenario(
                settings,
                scenario=scenario,
                seed=seed,
                duration_seconds=duration_seconds,
                rate_per_second=rate_per_second,
                concurrency=concurrency,
            )
            captures.append(capture)
            print(json.dumps({"capture": str(capture), "scenario": scenario}))
    for scenario_index, scenario in enumerate(CONTROL_SCENARIOS):
        capture = await run_scenario(
            settings,
            scenario=scenario,
            seed=9_000 + scenario_index,
            duration_seconds=duration_seconds,
            rate_per_second=rate_per_second,
            concurrency=concurrency,
        )
        captures.append(capture)
        print(json.dumps({"capture": str(capture), "scenario": scenario}))
    return captures


def main() -> None:
    parser = argparse.ArgumentParser(prog="incidentgraph-lab")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("migrate")
    subcommands.add_parser("wait-ready")
    workload_parser = subcommands.add_parser("workload")
    workload_parser.add_argument("--duration", type=float, default=6)
    workload_parser.add_argument("--rate", type=float, default=6)
    workload_parser.add_argument("--concurrency", type=int, default=4)
    workload_parser.add_argument("--seed", type=int, default=1)
    scenario_parser = subcommands.add_parser("scenario")
    scenario_parser.add_argument(
        "--scenario", choices=REQUIRED_FAULTS + CONTROL_SCENARIOS, required=True
    )
    scenario_parser.add_argument("--duration", type=int, default=6)
    scenario_parser.add_argument("--rate", type=float, default=6)
    scenario_parser.add_argument("--concurrency", type=int, default=4)
    scenario_parser.add_argument("--seed", type=int, default=1)
    suite_parser = subcommands.add_parser("capture-suite")
    suite_parser.add_argument("--duration", type=int, default=6)
    suite_parser.add_argument("--rate", type=float, default=6)
    suite_parser.add_argument("--concurrency", type=int, default=4)
    subcommands.add_parser("verify-captures")
    args = parser.parse_args()
    settings = LabOperatorSettings()  # type: ignore[call-arg]

    if args.command == "migrate":
        asyncio.run(migrate_lab(settings))
        print("lab migration 002_lab applied")
    elif args.command == "wait-ready":
        asyncio.run(wait_ready(settings))
        print("lab services ready")
    elif args.command == "workload":
        result = asyncio.run(
            run_workload(
                settings,
                duration_seconds=args.duration,
                rate_per_second=args.rate,
                concurrency=args.concurrency,
                seed=args.seed,
                prefix=f"manual-{uuid4().hex[:8]}",
            )
        )
        print(result.model_dump_json(indent=2))
    elif args.command == "scenario":
        capture = asyncio.run(
            run_scenario(
                settings,
                scenario=args.scenario,
                seed=args.seed,
                duration_seconds=args.duration,
                rate_per_second=args.rate,
                concurrency=args.concurrency,
            )
        )
        print(json.dumps({"capture": str(capture)}))
    elif args.command == "capture-suite":
        captures = asyncio.run(
            capture_suite(
                settings,
                duration_seconds=args.duration,
                rate_per_second=args.rate,
                concurrency=args.concurrency,
            )
        )
        print(json.dumps({"capture_count": len(captures)}))
    elif args.command == "verify-captures":
        verification = verify_capture_suite(
            settings.lab_capture_dir,
            settings.lab_evaluator_labels,
        )
        print(verification.model_dump_json(indent=2))
