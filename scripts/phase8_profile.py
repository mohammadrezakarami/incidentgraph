"""Capture a lightweight local API and container resource profile without model calls."""

from __future__ import annotations

import argparse
import json
import shutil
import statistics
import subprocess
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def memory_bytes(value: str) -> int | None:
    used = value.split("/", 1)[0].strip()
    units = {"KiB": 1024, "MiB": 1024**2, "GiB": 1024**3}
    for suffix, multiplier in units.items():
        if used.endswith(suffix):
            return round(float(used.removesuffix(suffix)) * multiplier)
    return None


def docker_stats() -> list[dict[str, Any]]:
    docker = shutil.which("docker")
    if docker is None:
        return [{"status": "unavailable", "reason": "docker executable not found"}]
    completed = subprocess.run(  # noqa: S603
        [docker, "stats", "--no-stream", "--format", "{{json .}}"],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    if completed.returncode != 0:
        return [{"status": "unavailable", "reason": "docker stats returned non-zero"}]
    rows: list[dict[str, Any]] = []
    for line in completed.stdout.splitlines():
        if line.strip():
            raw = json.loads(line)
            name = str(raw.get("Name", ""))
            if not name.startswith("incidentgraph-"):
                continue
            rows.append(
                {
                    "name": name,
                    "cpu_percent": raw.get("CPUPerc"),
                    "memory_usage": raw.get("MemUsage"),
                    "memory_usage_bytes": memory_bytes(str(raw.get("MemUsage", ""))),
                    "memory_percent": raw.get("MemPerc"),
                    "pids": raw.get("PIDs"),
                }
            )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000/health/live")
    parser.add_argument("--samples", type=int, default=25, choices=range(5, 101))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/observability/phase8-local-profile.json"),
    )
    arguments = parser.parse_args()

    durations: list[float] = []
    failures = 0
    for _ in range(arguments.samples):
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(arguments.url, timeout=2) as response:  # noqa: S310
                if response.status != 200:
                    failures += 1
                response.read()
        except OSError:
            failures += 1
        durations.append((time.perf_counter() - started) * 1_000)

    containers = docker_stats()
    measured_bytes = [
        row["memory_usage_bytes"]
        for row in containers
        if isinstance(row.get("memory_usage_bytes"), int)
    ]
    result = {
        "captured_at": datetime.now(UTC).isoformat(),
        "scope": "lightweight local health endpoint; no model, GPU, or load generator",
        "url": arguments.url,
        "sample_count": len(durations),
        "failure_count": failures,
        "latency_ms": {
            "min": min(durations),
            "median": statistics.median(durations),
            "p95": percentile(durations, 0.95),
            "max": max(durations),
        },
        "container_memory_total_bytes": sum(measured_bytes) if measured_bytes else None,
        "containers": containers,
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
