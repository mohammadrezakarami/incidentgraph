from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from incidentgraph.capture_verification import verify_capture_suite
from incidentgraph.ingestion import ROOT

CAPTURE_ROOT = ROOT / "data" / "captures-v3"
SOURCE_LABEL_PATH = ROOT / "data" / "evaluator" / "phase9-v3-capture-labels.jsonl"
CASE_PATH = ROOT / "data" / "evaluation" / "incident-cases-v3.jsonl"
LABEL_PATH = ROOT / "data" / "evaluator" / "incident-labels-v3.jsonl"
SEAL_PATH = ROOT / "data" / "evaluator" / "incident-heldout-seal-v3.json"
CORPUS_MANIFEST = ROOT / "data" / "corpus" / "manifest.jsonl"

IDENTIFIABLE_COUNTS = {
    "downstream_latency": 3,
    "pool_exhaustion": 3,
    "dependency_errors": 3,
    "cache_degradation": 3,
    "deployment_regression": 3,
    "resource_contention": 3,
    "misleading_correlation": 2,
}
HEALTHY_COUNTS = {"healthy": 3, "healthy_high_traffic": 2}
INSUFFICIENT_COUNTS = {"incomplete_telemetry": 3, "ambiguous_two_cause": 2}
TARGET_SERVICE = {
    "downstream_latency": "gateway",
    "pool_exhaustion": "checkout",
    "dependency_errors": "gateway",
    "cache_degradation": "payments",
    "deployment_regression": "checkout",
    "resource_contention": "payments",
    "misleading_correlation": "gateway",
    "healthy": "gateway",
    "healthy_high_traffic": "gateway",
    "incomplete_telemetry": "gateway",
    "ambiguous_two_cause": "gateway",
}
QUESTIONS = (
    "What best explains the service symptoms in this bounded replay window?",
    "Investigate the dominant failure or latency mechanism without assuming a cause.",
    "Which component and mechanism are supported by the available observations?",
)
HEALTHY_QUESTIONS = (
    "Determine whether this window contains an incident or normal behavior.",
    "Investigate the concern without asserting an unsupported incident.",
    "Produce a cited diagnosis, including a no-incident result when appropriate.",
)
INSUFFICIENT_QUESTIONS = (
    "Investigate the symptom, but abstain if required telemetry is unavailable.",
    "Produce a diagnosis only if the evidence distinguishes one bounded cause.",
    "State the missing or competing evidence instead of guessing a cause.",
)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _canonical(item: Any) -> str:
    return json.dumps(item, separators=(",", ":"), sort_keys=True)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _capture_pairs(
    labels: list[dict[str, Any]],
) -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for label in labels:
        grouped[str(label["scenario"])].append(label)
    required = set(IDENTIFIABLE_COUNTS) | set(HEALTHY_COUNTS) | set(INSUFFICIENT_COUNTS)
    pairs: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for scenario in sorted(required):
        candidates = sorted(grouped[scenario], key=lambda item: (item["seed"], item["capture_id"]))
        if len(candidates) != 2:
            raise ValueError(f"v3 requires exactly two fresh captures for {scenario}")
        pairs[scenario] = (candidates[0], candidates[1])
    return pairs


def _case_and_label(
    *,
    case_id: str,
    split: str,
    source: dict[str, Any],
    question: str,
    case_type: str,
    variant_index: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    scenario = str(source["scenario"])
    case = {
        "case_id": case_id,
        "split": split,
        "group_id": source["capture_id"],
        "question": question,
        "target_service": TARGET_SERVICE[scenario],
        "environment": "lab",
        "window_start": source["observation_start"],
        "window_end": source["observation_cutoff"],
        "observation_cutoff": source["observation_cutoff"],
        "snapshot_id": source["capture_id"],
        "provenance_category": "independent_lab_capture",
        "variant_index": variant_index,
    }
    if case_type == "insufficient":
        accepted_components: list[str] = []
        accepted_mechanisms = ["insufficient_observation"]
        answerability = "insufficient_observation"
        annotations: dict[str, Any] = {
            "required_missing_information": [
                "direct telemetry for the affected dependency or evidence distinguishing causes"
            ]
        }
    else:
        accepted_components = list(source["accepted_components"])
        accepted_mechanisms = list(source["accepted_mechanisms"])
        answerability = "healthy" if case_type == "healthy" else source["answerability"]
        annotations = dict(source["bounded_impact"])
    label = {
        "case_id": case_id,
        "case_type": case_type,
        "answerability": answerability,
        "accepted_components": accepted_components,
        "accepted_mechanisms": accepted_mechanisms,
        "evidence_annotations": annotations,
        "source_capture_id": source["capture_id"],
    }
    return case, label


def build_fixture(
    source_labels_path: Path = SOURCE_LABEL_PATH,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_labels = _jsonl(source_labels_path)
    pairs = _capture_pairs(source_labels)
    cases: list[dict[str, Any]] = []
    labels: list[dict[str, Any]] = []
    for split, pair_index in (("dev", 0), ("heldout", 1)):
        number = 1
        for case_type, counts, questions in (
            ("identifiable", IDENTIFIABLE_COUNTS, QUESTIONS),
            ("healthy", HEALTHY_COUNTS, HEALTHY_QUESTIONS),
            ("insufficient", INSUFFICIENT_COUNTS, INSUFFICIENT_QUESTIONS),
        ):
            for scenario, count in counts.items():
                source = pairs[scenario][pair_index]
                for variant_index in range(count):
                    case_id = f"incident-v3-{split}-{number:03d}"
                    case, label = _case_and_label(
                        case_id=case_id,
                        split=split,
                        source=source,
                        question=questions[variant_index],
                        case_type=case_type,
                        variant_index=variant_index,
                    )
                    cases.append(case)
                    labels.append(label)
                    number += 1
    return cases, labels


def validate_fixture(
    cases: list[dict[str, Any]],
    labels: list[dict[str, Any]],
    capture_root: Path = CAPTURE_ROOT,
) -> None:
    case_ids = {item["case_id"] for item in cases}
    label_ids = {item["case_id"] for item in labels}
    if len(cases) != 60 or len(labels) != 60 or case_ids != label_ids:
        raise ValueError("v3 fixture requires 60 matching cases and labels")
    labels_by_id = {item["case_id"]: item for item in labels}
    for split in ("dev", "heldout"):
        split_cases = [item for item in cases if item["split"] == split]
        counts = Counter(labels_by_id[item["case_id"]]["case_type"] for item in split_cases)
        if counts != {"identifiable": 20, "healthy": 5, "insufficient": 5}:
            raise ValueError(f"invalid {split} v3 distribution: {dict(counts)}")
    dev_groups = {item["group_id"] for item in cases if item["split"] == "dev"}
    heldout_groups = {item["group_id"] for item in cases if item["split"] == "heldout"}
    if dev_groups.intersection(heldout_groups):
        raise ValueError("fresh capture groups cross the v3 split boundary")
    corpus_cutoff = max(
        datetime.fromisoformat(item["valid_from"].replace("Z", "+00:00"))
        for item in _jsonl(CORPUS_MANIFEST)
    )
    for case in cases:
        if not (capture_root / case["snapshot_id"] / "MANIFEST.sha256").is_file():
            raise ValueError(f"missing sealed snapshot: {case['snapshot_id']}")
        if datetime.fromisoformat(case["window_start"]) < corpus_cutoff:
            raise ValueError(f"capture predates corpus baseline: {case['snapshot_id']}")


def heldout_digest(cases: list[dict[str, Any]], labels: list[dict[str, Any]]) -> str:
    heldout_cases = [item for item in cases if item["split"] == "heldout"]
    heldout_ids = {item["case_id"] for item in heldout_cases}
    heldout_labels = [item for item in labels if item["case_id"] in heldout_ids]
    payload = {
        "cases": heldout_cases,
        "labels": heldout_labels,
        "capture_manifests": {
            snapshot_id: _sha256(CAPTURE_ROOT / snapshot_id / "MANIFEST.sha256")
            for snapshot_id in sorted({item["snapshot_id"] for item in heldout_cases})
        },
        "corpus_manifest_sha256": _sha256(CORPUS_MANIFEST),
    }
    return hashlib.sha256(_canonical(payload).encode()).hexdigest()


def write_fixture() -> dict[str, Any]:
    existing = [path for path in (CASE_PATH, LABEL_PATH, SEAL_PATH) if path.exists()]
    if existing:
        raise FileExistsError("v3 fixture already exists; refusing to overwrite a sealed dataset")
    capture_verification = verify_capture_suite(CAPTURE_ROOT, SOURCE_LABEL_PATH)
    cases, labels = build_fixture()
    validate_fixture(cases, labels)
    CASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    LABEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    CASE_PATH.write_text("\n".join(_canonical(item) for item in cases) + "\n", encoding="utf-8")
    LABEL_PATH.write_text("\n".join(_canonical(item) for item in labels) + "\n", encoding="utf-8")
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
        "status": "sealed-before-phase9-v3-model-evaluation",
        "capture_verification": capture_verification.model_dump(mode="json"),
    }
    SEAL_PATH.write_text(json.dumps(seal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"status": "sealed", "digest": digest, "total_cases": 60}


def verify_fixture() -> dict[str, Any]:
    cases = _jsonl(CASE_PATH)
    labels = _jsonl(LABEL_PATH)
    validate_fixture(cases, labels)
    seal = json.loads(SEAL_PATH.read_text(encoding="utf-8"))
    actual = heldout_digest(cases, labels)
    if actual != seal["digest"]:
        raise ValueError("Phase 9 v3 held-out data no longer matches its seal")
    return {
        "status": "pass",
        "digest": actual,
        "total_cases": len(cases),
        "dev_cases": 30,
        "heldout_cases": 30,
        "heldout_evaluated": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or verify Phase 9 v3 fresh evaluation data")
    parser.add_argument("command", choices=("build", "verify"))
    args = parser.parse_args()
    result = write_fixture() if args.command == "build" else verify_fixture()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
