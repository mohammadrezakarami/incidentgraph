from __future__ import annotations

import json
from pathlib import Path

from incidentgraph.phase9_v3_dataset import (
    HEALTHY_COUNTS,
    IDENTIFIABLE_COUNTS,
    INSUFFICIENT_COUNTS,
    build_fixture,
)


def _source_label(scenario: str, run: int) -> dict[str, object]:
    return {
        "capture_id": f"cap-20260928{run:02d}0000-{scenario[:10]:0<10}",
        "scenario": scenario,
        "seed": run,
        "answerability": (
            "insufficient_observation"
            if scenario in {"incomplete_telemetry", "ambiguous_two_cause"}
            else "answerable"
        ),
        "accepted_components": []
        if scenario.startswith(("healthy", "incomplete", "ambiguous"))
        else ["payments"],
        "accepted_mechanisms": (
            ["insufficient_observation"]
            if scenario in {"incomplete_telemetry", "ambiguous_two_cause"}
            else ["healthy"]
            if scenario.startswith("healthy")
            else [scenario]
        ),
        "bounded_impact": {"failure_count": 0},
        "observation_start": "2026-09-28T00:00:00+00:00",
        "observation_cutoff": "2026-09-28T00:01:00+00:00",
    }


def test_v3_builder_uses_disjoint_fresh_capture_groups(tmp_path: Path) -> None:
    scenarios = set(IDENTIFIABLE_COUNTS) | set(HEALTHY_COUNTS) | set(INSUFFICIENT_COUNTS)
    source_path = tmp_path / "labels.jsonl"
    rows = [_source_label(scenario, run) for scenario in sorted(scenarios) for run in (1, 2)]
    source_path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )

    cases, labels = build_fixture(source_path)

    assert len(cases) == len(labels) == 60
    dev_groups = {item["group_id"] for item in cases if item["split"] == "dev"}
    heldout_groups = {item["group_id"] for item in cases if item["split"] == "heldout"}
    assert len(dev_groups) == len(heldout_groups) == 11
    assert not dev_groups.intersection(heldout_groups)
    counts = {
        split: {
            case_type: sum(
                1
                for label in labels
                if label["case_id"].startswith(f"incident-v3-{split}")
                and label["case_type"] == case_type
            )
            for case_type in ("identifiable", "healthy", "insufficient")
        }
        for split in ("dev", "heldout")
    }
    assert counts == {
        "dev": {"identifiable": 20, "healthy": 5, "insufficient": 5},
        "heldout": {"identifiable": 20, "healthy": 5, "insufficient": 5},
    }
