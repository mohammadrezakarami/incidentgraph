"""Write the compact, frozen Phase 9 core-coverage measurement."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCOPE = [
    "incidentgraph.models",
    "incidentgraph.auth",
    "incidentgraph.api_support",
    "incidentgraph.investigation_tools",
    "incidentgraph.investigator",
    "incidentgraph.retrieval",
    "incidentgraph.phase9_repair",
    "incidentgraph.phase9_v4_evaluation",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    raw: dict[str, Any] = json.loads(args.input.read_text(encoding="utf-8"))
    document = {
        "schema_version": 1,
        "measured_at": datetime.now(UTC).isoformat(),
        "branch_coverage": True,
        "scope": SCOPE,
        "test_selector": 'pytest -m "not integration"',
        "totals": raw["totals"],
        "files": {
            Path(path).name: value["summary"]
            for path, value in sorted(raw["files"].items())
        },
    }
    args.output.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(document["totals"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
