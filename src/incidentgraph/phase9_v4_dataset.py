"""Build and verify the fresh post-repair Phase 9 v4 held-out fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from incidentgraph.capture_verification import verify_capture_suite
from incidentgraph.ingestion import ROOT
from incidentgraph.phase9_v3_dataset import (
    HEALTHY_COUNTS,
    HEALTHY_QUESTIONS,
    IDENTIFIABLE_COUNTS,
    INSUFFICIENT_COUNTS,
    INSUFFICIENT_QUESTIONS,
    QUESTIONS,
    TARGET_SERVICE,
)

CAPTURE_ROOT = ROOT / "data" / "captures-v4"
SOURCE_LABEL_PATH = ROOT / "data" / "evaluator" / "phase9-v4-capture-labels.jsonl"
CASE_PATH = ROOT / "data" / "evaluation" / "incident-cases-v4.jsonl"
LABEL_PATH = ROOT / "data" / "evaluator" / "incident-labels-v4.jsonl"
SEAL_PATH = ROOT / "data" / "evaluator" / "incident-heldout-seal-v4.json"
CORPUS_MANIFEST = ROOT / "data" / "corpus" / "manifest.jsonl"


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _canonical(item: Any) -> str:
    return json.dumps(item, separators=(",", ":"), sort_keys=True)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_fixture() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_by_scenario = {str(item["scenario"]): item for item in _jsonl(SOURCE_LABEL_PATH)}
    required = set(IDENTIFIABLE_COUNTS) | set(HEALTHY_COUNTS) | set(INSUFFICIENT_COUNTS)
    if set(source_by_scenario) != required:
        raise ValueError("v4 requires exactly one new capture for each of the 11 scenarios")
    cases: list[dict[str, Any]] = []
    labels: list[dict[str, Any]] = []
    number = 1
    for case_type, counts, questions in (
        ("identifiable", IDENTIFIABLE_COUNTS, QUESTIONS),
        ("healthy", HEALTHY_COUNTS, HEALTHY_QUESTIONS),
        ("insufficient", INSUFFICIENT_COUNTS, INSUFFICIENT_QUESTIONS),
    ):
        for scenario, count in counts.items():
            source = source_by_scenario[scenario]
            for variant_index in range(count):
                case_id = f"incident-v4-heldout-{number:03d}"
                cases.append(
                    {
                        "case_id": case_id,
                        "split": "heldout",
                        "group_id": source["capture_id"],
                        "question": questions[variant_index],
                        "target_service": TARGET_SERVICE[scenario],
                        "environment": "lab",
                        "window_start": source["observation_start"],
                        "window_end": source["observation_cutoff"],
                        "observation_cutoff": source["observation_cutoff"],
                        "snapshot_id": source["capture_id"],
                        "provenance_category": "independent_post_repair_lab_capture",
                        "variant_index": variant_index,
                    }
                )
                if case_type == "insufficient":
                    accepted_components: list[str] = []
                    accepted_mechanisms = ["insufficient_observation"]
                    answerability = "insufficient_observation"
                    annotations: dict[str, Any] = {
                        "required_missing_information": [
                            "direct telemetry for the affected dependency or evidence "
                            "distinguishing causes"
                        ]
                    }
                else:
                    accepted_components = list(source["accepted_components"])
                    accepted_mechanisms = list(source["accepted_mechanisms"])
                    answerability = "healthy" if case_type == "healthy" else "answerable"
                    annotations = dict(source["bounded_impact"])
                labels.append(
                    {
                        "case_id": case_id,
                        "case_type": case_type,
                        "answerability": answerability,
                        "accepted_components": accepted_components,
                        "accepted_mechanisms": accepted_mechanisms,
                        "evidence_annotations": annotations,
                        "source_capture_id": source["capture_id"],
                    }
                )
                number += 1
    return cases, labels


def validate_fixture(cases: list[dict[str, Any]], labels: list[dict[str, Any]]) -> None:
    if len(cases) != 30 or len(labels) != 30:
        raise ValueError("v4 fixture requires 30 cases and 30 labels")
    case_ids = {item["case_id"] for item in cases}
    if case_ids != {item["case_id"] for item in labels}:
        raise ValueError("v4 case and label IDs differ")
    labels_by_id = {item["case_id"]: item for item in labels}
    distribution = Counter(labels_by_id[item["case_id"]]["case_type"] for item in cases)
    if distribution != {"identifiable": 20, "healthy": 5, "insufficient": 5}:
        raise ValueError(f"invalid v4 distribution: {dict(distribution)}")
    if len({item["group_id"] for item in cases}) != 11:
        raise ValueError("v4 cases must preserve 11 independent capture groups")
    corpus_cutoff = max(
        datetime.fromisoformat(item["valid_from"].replace("Z", "+00:00"))
        for item in _jsonl(CORPUS_MANIFEST)
    )
    for case in cases:
        if case["split"] != "heldout":
            raise ValueError("v4 contains only a fresh held-out split")
        if not (CAPTURE_ROOT / case["snapshot_id"] / "MANIFEST.sha256").is_file():
            raise ValueError(f"missing v4 snapshot: {case['snapshot_id']}")
        if datetime.fromisoformat(case["window_start"]) < corpus_cutoff:
            raise ValueError(f"v4 capture predates corpus baseline: {case['snapshot_id']}")


def heldout_digest(cases: list[dict[str, Any]], labels: list[dict[str, Any]]) -> str:
    payload = {
        "cases": cases,
        "labels": labels,
        "capture_manifests": {
            snapshot_id: _sha256(CAPTURE_ROOT / snapshot_id / "MANIFEST.sha256")
            for snapshot_id in sorted({item["snapshot_id"] for item in cases})
        },
        "corpus_manifest_sha256": _sha256(CORPUS_MANIFEST),
    }
    return hashlib.sha256(_canonical(payload).encode()).hexdigest()


def write_fixture() -> dict[str, Any]:
    if any(path.exists() for path in (CASE_PATH, LABEL_PATH, SEAL_PATH)):
        raise FileExistsError("v4 fixture already exists; refusing to overwrite sealed data")
    verification = verify_capture_suite(
        CAPTURE_ROOT,
        SOURCE_LABEL_PATH,
        minimum_fault_captures=1,
    )
    cases, labels = build_fixture()
    validate_fixture(cases, labels)
    CASE_PATH.write_text("\n".join(_canonical(item) for item in cases) + "\n", encoding="utf-8")
    LABEL_PATH.write_text(
        "\n".join(_canonical(item) for item in labels) + "\n", encoding="utf-8"
    )
    digest = heldout_digest(cases, labels)
    seal = {
        "schema_version": 1,
        "split": "heldout",
        "case_count": 30,
        "label_count": 30,
        "distribution": {"identifiable": 20, "insufficient": 5, "healthy": 5},
        "independent_capture_groups": 11,
        "hash_algorithm": "sha256",
        "digest": digest,
        "sealed_at": datetime.now(UTC).isoformat(),
        "status": "sealed-before-phase9-v4-model-evaluation",
        "capture_verification": verification.model_dump(mode="json"),
    }
    SEAL_PATH.write_text(json.dumps(seal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"status": "sealed", "digest": digest, "heldout_cases": len(cases)}


def verify_fixture() -> dict[str, Any]:
    cases = _jsonl(CASE_PATH)
    labels = _jsonl(LABEL_PATH)
    validate_fixture(cases, labels)
    seal = json.loads(SEAL_PATH.read_text(encoding="utf-8"))
    actual = heldout_digest(cases, labels)
    if actual != seal["digest"]:
        raise ValueError("Phase 9 v4 held-out data no longer matches its seal")
    return {
        "status": "pass",
        "digest": actual,
        "heldout_cases": len(cases),
        "heldout_evaluated": False,
        "independent_capture_groups": 11,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or verify Phase 9 v4 fresh heldout data")
    parser.add_argument("command", choices=("build", "verify"))
    args = parser.parse_args()
    result = write_fixture() if args.command == "build" else verify_fixture()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
