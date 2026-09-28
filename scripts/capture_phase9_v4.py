"""Capture one bounded post-repair run for each Phase 9 v4 scenario."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from incidentgraph.lab_cli import (
    CONTROL_SCENARIOS,
    REQUIRED_FAULTS,
    LabOperatorSettings,
    run_scenario,
)

CAPTURE_ROOT = Path("data/captures-v4")
LABEL_PATH = Path("data/evaluator/phase9-v4-capture-labels.jsonl")


async def main() -> None:
    capture_exists, label_exists = await asyncio.gather(
        asyncio.to_thread(CAPTURE_ROOT.exists),
        asyncio.to_thread(LABEL_PATH.exists),
    )
    if capture_exists or label_exists:
        raise FileExistsError("Phase 9 v4 capture output already exists; refusing to overwrite it")
    settings = LabOperatorSettings().model_copy(
        update={
            "lab_capture_dir": CAPTURE_ROOT,
            "lab_evaluator_labels": LABEL_PATH,
        }
    )
    captures: list[str] = []
    scenarios = (*REQUIRED_FAULTS, *CONTROL_SCENARIOS)
    for index, scenario in enumerate(scenarios):
        capture = await run_scenario(
            settings,
            scenario=scenario,
            seed=40_000 + index * 137,
            duration_seconds=6,
            rate_per_second=6,
            concurrency=4,
        )
        captures.append(str(capture))
        print(
            json.dumps(
                {
                    "completed": len(captures),
                    "total": len(scenarios),
                    "scenario": scenario,
                    "capture": str(capture),
                }
            ),
            flush=True,
        )
    print(json.dumps({"status": "complete", "capture_count": len(captures)}))


if __name__ == "__main__":
    asyncio.run(main())
