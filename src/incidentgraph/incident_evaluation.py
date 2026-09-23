from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from incidentgraph.ingestion import ROOT

CASE_PATH = ROOT / "data" / "evaluation" / "incident-cases-v1.jsonl"
LABEL_PATH = ROOT / "data" / "evaluator" / "incident-labels-v1.jsonl"
SEAL_PATH = ROOT / "data" / "evaluator" / "incident-heldout-seal-v1.json"
PHASE2_LABEL_PATH = ROOT / "data" / "evaluator" / "phase2-labels.jsonl"

FAULT_PAIRS = (
    (
        "cap-20260922214548-14c491f743",
        "cap-20260922214559-d9887d26ba",
        4,
        "gateway",
    ),
    (
        "cap-20260922214609-1f2ab5574e",
        "cap-20260922214620-36faad708e",
        4,
        "checkout",
    ),
    (
        "cap-20260922214631-8a73e79c0b",
        "cap-20260922214641-7cce3b800a",
        3,
        "gateway",
    ),
    (
        "cap-20260922214652-c051b539f3",
        "cap-20260922214702-adeec2b9d2",
        3,
        "payments",
    ),
    (
        "cap-20260922214713-1d16da3def",
        "cap-20260922214724-ce2dfb287b",
        3,
        "checkout",
    ),
    (
        "cap-20260922214734-04c5ecfcf0",
        "cap-20260922214745-7b4b000470",
        3,
        "payments",
    ),
)

QUESTION_TEMPLATES = (
    "What best explains the service symptoms in this bounded replay window?",
    "Investigate the dominant failure or latency mechanism without assuming a cause.",
    "Which component and mechanism are supported by the available observations?",
    "Produce a cited diagnosis or abstain if the evidence is insufficient.",
)

CONTROL_QUESTIONS = (
    "Determine whether this window contains an incident or normal behavior.",
    "Investigate the reported concern and avoid asserting an unsupported incident.",
    "Are the observed signals evidence of a fault? Provide a cited result.",
    "Assess this window for an identifiable operational problem.",
    "Produce a bounded report, including a no-incident outcome when appropriate.",
)

INSUFFICIENT_QUESTIONS = (
    "Investigate the reported symptom, but abstain if critical telemetry is unavailable.",
    "Can a specific component and mechanism be supported from this observation window?",
    "Produce a diagnosis only if the available evidence distinguishes plausible causes.",
    "State what information is missing if this replay cannot support a cause.",
    "Assess the incident without filling telemetry gaps with assumptions.",
)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _source_labels() -> dict[str, dict[str, Any]]:
    return {item["capture_id"]: item for item in _jsonl(PHASE2_LABEL_PATH)}


def build_fixture() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source = _source_labels()
    cases: list[dict[str, Any]] = []
    labels: list[dict[str, Any]] = []

    for split, capture_index in (("dev", 0), ("heldout", 1)):
        number = 1
        for dev_capture, heldout_capture, count, target_service in FAULT_PAIRS:
            capture_id = dev_capture if capture_index == 0 else heldout_capture
            label = source[capture_id]
            for variant in range(count):
                case_id = f"incident-{split}-{number:03d}"
                cases.append(
                    {
                        "case_id": case_id,
                        "split": split,
                        "group_id": capture_id,
                        "question": QUESTION_TEMPLATES[variant],
                        "target_service": target_service,
                        "environment": "lab",
                        "window_start": label["observation_start"],
                        "window_end": label["observation_cutoff"],
                        "observation_cutoff": label["observation_cutoff"],
                        "snapshot_id": capture_id,
                        "provenance_category": "independent_lab_capture",
                        "variant_index": variant,
                    }
                )
                labels.append(
                    {
                        "case_id": case_id,
                        "case_type": "identifiable",
                        "answerability": label["answerability"],
                        "accepted_components": label["accepted_components"],
                        "accepted_mechanisms": label["accepted_mechanisms"],
                        "evidence_annotations": label["bounded_impact"],
                        "source_capture_id": capture_id,
                    }
                )
                number += 1

        healthy_capture = (
            "cap-20260922214755-699290fa11" if split == "dev" else "cap-20260922214806-0f4186df57"
        )
        healthy_label = source[healthy_capture]
        for variant, question in enumerate(CONTROL_QUESTIONS):
            case_id = f"incident-{split}-{number:03d}"
            cases.append(
                {
                    "case_id": case_id,
                    "split": split,
                    "group_id": healthy_capture,
                    "question": question,
                    "target_service": "gateway",
                    "environment": "lab",
                    "window_start": healthy_label["observation_start"],
                    "window_end": healthy_label["observation_cutoff"],
                    "observation_cutoff": healthy_label["observation_cutoff"],
                    "snapshot_id": healthy_capture,
                    "provenance_category": "independent_lab_capture",
                    "variant_index": variant,
                }
            )
            labels.append(
                {
                    "case_id": case_id,
                    "case_type": "healthy",
                    "answerability": "healthy",
                    "accepted_components": [],
                    "accepted_mechanisms": healthy_label["accepted_mechanisms"],
                    "evidence_annotations": healthy_label["bounded_impact"],
                    "source_capture_id": healthy_capture,
                }
            )
            number += 1

        insufficient_capture = (
            "cap-20260922214827-4a2d6b66c2" if split == "dev" else "cap-20260922214837-95f00263c2"
        )
        insufficient_label = source[insufficient_capture]
        for variant, question in enumerate(INSUFFICIENT_QUESTIONS):
            case_id = f"incident-{split}-{number:03d}"
            transform_id = "none" if split == "dev" else f"tx-held-mask-{variant + 1:02d}"
            cases.append(
                {
                    "case_id": case_id,
                    "split": split,
                    "group_id": insufficient_capture,
                    "question": question,
                    "target_service": "gateway",
                    "environment": "lab",
                    "window_start": insufficient_label["observation_start"],
                    "window_end": insufficient_label["observation_cutoff"],
                    "observation_cutoff": insufficient_label["observation_cutoff"],
                    "snapshot_id": insufficient_capture,
                    "provenance_category": (
                        "independent_lab_capture" if split == "dev" else "transformed_capture"
                    ),
                    "transform_id": transform_id,
                    "variant_index": variant,
                }
            )
            labels.append(
                {
                    "case_id": case_id,
                    "case_type": "insufficient",
                    "answerability": "insufficient_observation",
                    "accepted_components": [],
                    "accepted_mechanisms": ["insufficient_observation"],
                    "evidence_annotations": {
                        "required_missing_information": [
                            "independent evidence that distinguishes the plausible causes"
                        ]
                    },
                    "source_capture_id": insufficient_capture,
                    "transform_id": transform_id,
                }
            )
            number += 1
    return cases, labels


def _line(item: dict[str, Any]) -> str:
    return json.dumps(item, sort_keys=True, separators=(",", ":"))


def heldout_digest(cases: list[dict[str, Any]], labels: list[dict[str, Any]]) -> str:
    heldout_cases = [_line(item) for item in cases if item["split"] == "heldout"]
    heldout_ids = {json.loads(line)["case_id"] for line in heldout_cases}
    heldout_labels = [_line(item) for item in labels if item["case_id"] in heldout_ids]
    payload = "\n".join(heldout_cases) + "\n---LABELS---\n" + "\n".join(heldout_labels) + "\n"
    return hashlib.sha256(payload.encode()).hexdigest()


def validate_fixture(cases: list[dict[str, Any]], labels: list[dict[str, Any]]) -> None:
    case_ids = {item["case_id"] for item in cases}
    label_ids = {item["case_id"] for item in labels}
    if len(cases) != 60 or len(labels) != 60 or case_ids != label_ids:
        raise ValueError("incident fixture requires 60 matching cases and labels")
    labels_by_id = {item["case_id"]: item for item in labels}
    for split in ("dev", "heldout"):
        split_cases = [item for item in cases if item["split"] == split]
        counts = {"identifiable": 0, "healthy": 0, "insufficient": 0}
        for item in split_cases:
            counts[labels_by_id[item["case_id"]]["case_type"]] += 1
        if len(split_cases) != 30 or counts != {
            "identifiable": 20,
            "healthy": 5,
            "insufficient": 5,
        }:
            raise ValueError(f"invalid {split} incident distribution: {counts}")
    dev_groups = {item["group_id"] for item in cases if item["split"] == "dev"}
    heldout_groups = {item["group_id"] for item in cases if item["split"] == "heldout"}
    if dev_groups.intersection(heldout_groups):
        raise ValueError("related incident groups cross the split boundary")


def write_fixture() -> dict[str, Any]:
    cases, labels = build_fixture()
    validate_fixture(cases, labels)
    CASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    LABEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    CASE_PATH.write_text("\n".join(_line(item) for item in cases) + "\n", encoding="utf-8")
    LABEL_PATH.write_text("\n".join(_line(item) for item in labels) + "\n", encoding="utf-8")
    digest = heldout_digest(cases, labels)
    seal = {
        "schema_version": 1,
        "split": "heldout",
        "case_count": 30,
        "label_count": 30,
        "distribution": {"identifiable": 20, "insufficient": 5, "healthy": 5},
        "hash_algorithm": "sha256",
        "digest": digest,
        "sealed_at": "2026-09-23T12:00:00Z",
        "status": "sealed-before-phase5-development-tuning",
    }
    SEAL_PATH.write_text(json.dumps(seal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return seal


def verify_fixture() -> dict[str, Any]:
    cases = _jsonl(CASE_PATH)
    labels = _jsonl(LABEL_PATH)
    validate_fixture(cases, labels)
    seal = json.loads(SEAL_PATH.read_text(encoding="utf-8"))
    actual = heldout_digest(cases, labels)
    if actual != seal["digest"]:
        raise ValueError("incident held-out data no longer matches its seal")
    return {
        "status": "pass",
        "digest": actual,
        "total_cases": len(cases),
        "dev_cases": 30,
        "heldout_cases": 30,
        "heldout_evaluated": False,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Build or verify sealed incident evaluation data")
    parser.add_argument("command", choices=("build", "verify"))
    args = parser.parse_args()
    result = write_fixture() if args.command == "build" else verify_fixture()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
