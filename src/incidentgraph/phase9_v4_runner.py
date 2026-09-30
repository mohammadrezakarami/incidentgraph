"""Frozen Phase 9 v4 post-repair evaluation orchestration and aggregation."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from incidentgraph.config import Settings
from incidentgraph.phase9_evaluation import (
    WORKFLOWS,
    _aggregate_agent,
    _canonical,
    _git_revision,
    _jsonl,
    _sha256,
    runtime_identity,
    score_incident_run,
)
from incidentgraph.phase9_repair import POLICY_VERSION
from incidentgraph.phase9_v2_evaluation import _settings
from incidentgraph.phase9_v3_dataset import (
    CASE_PATH as DEV_CASE_PATH,
)
from incidentgraph.phase9_v3_dataset import (
    LABEL_PATH as DEV_LABEL_PATH,
)
from incidentgraph.phase9_v3_evaluation import DEV_REPEAT_CASE_IDS, LocalStructuredV3Model
from incidentgraph.phase9_v4_dataset import (
    CAPTURE_ROOT,
    CASE_PATH,
    LABEL_PATH,
    SEAL_PATH,
    verify_fixture,
)
from incidentgraph.phase9_v4_evaluation import (
    WORKFLOW_VERSION,
    run_adaptive_case,
    run_fixed_case,
)

ROOT = Path(__file__).resolve().parents[2]
FREEZE_PATH = ROOT / "config" / "phase9-v4-fresh-freeze.json"
COVERAGE_PATH = ROOT / "config" / "phase9-v4-core-coverage.json"
DEFAULT_RUN_DIR = ROOT / "artifacts" / "evaluation" / "phase9-v4-fresh"
FREEZE_ID = "phase9-v4-fresh-post-repair"
RUN_PLAN_VERSION = "phase9-v4-free-colab-repair3-v1"
EXPECTED_JOB_COUNT = 120


def agent_jobs() -> list[dict[str, Any]]:
    development = {item["case_id"]: item for item in _jsonl(DEV_CASE_PATH)}
    heldout = _jsonl(CASE_PATH)
    jobs: list[dict[str, Any]] = []
    for repeat in range(1, 4):
        for case_id in DEV_REPEAT_CASE_IDS:
            for workflow in WORKFLOWS:
                jobs.append(
                    {
                        "job_id": f"dev-r{repeat}-{workflow}-{case_id}",
                        "split": "dev",
                        "repeat": repeat,
                        "workflow": workflow,
                        "case": development[case_id],
                    }
                )
    for case in heldout:
        for workflow in WORKFLOWS:
            jobs.append(
                {
                    "job_id": f"heldout-r1-{workflow}-{case['case_id']}",
                    "split": "heldout",
                    "repeat": 1,
                    "workflow": workflow,
                    "case": case,
                }
            )
    if len(jobs) != EXPECTED_JOB_COUNT:
        raise ValueError(f"Phase 9 v4 requires {EXPECTED_JOB_COUNT} jobs, found {len(jobs)}")
    return jobs


def frozen_paths() -> tuple[Path, ...]:
    capture_manifests = tuple(sorted(CAPTURE_ROOT.glob("*/MANIFEST.sha256")))
    return (
        CASE_PATH,
        LABEL_PATH,
        SEAL_PATH,
        ROOT / "data" / "corpus" / "manifest.jsonl",
        ROOT / "config" / "topology.json",
        COVERAGE_PATH,
        ROOT / "src" / "incidentgraph" / "capture_verification.py",
        ROOT / "src" / "incidentgraph" / "phase9_repair.py",
        ROOT / "src" / "incidentgraph" / "phase9_v2_evaluation.py",
        ROOT / "src" / "incidentgraph" / "phase9_v3_evaluation.py",
        ROOT / "src" / "incidentgraph" / "phase9_v4_dataset.py",
        ROOT / "src" / "incidentgraph" / "phase9_v4_evaluation.py",
        ROOT / "src" / "incidentgraph" / "phase9_v4_runner.py",
        ROOT / "src" / "incidentgraph" / "investigation_tools.py",
        ROOT / "src" / "incidentgraph" / "investigator.py",
        ROOT / "src" / "incidentgraph" / "models.py",
        ROOT / "uv.lock",
        *capture_manifests,
    )


def freeze_document() -> dict[str, Any]:
    coverage = json.loads(COVERAGE_PATH.read_text(encoding="utf-8"))
    return {
        "schema_version": 1,
        "freeze_id": FREEZE_ID,
        "state": "fresh-post-repair-heldout-sealed",
        "frozen_at": datetime.now(UTC).isoformat(),
        "git_revision": _git_revision(),
        "heldout_seal": verify_fixture(),
        "file_sha256": {str(path.relative_to(ROOT)): _sha256(path) for path in frozen_paths()},
        "model": {
            "provider": "local_openai_compatible",
            "requested_id": "qwen3:4b-instruct-2507-q4_K_M",
            "maximum_calls_per_adaptive_case": 1,
            "maximum_calls_per_fixed_case": 0,
            "maximum_tool_calls_per_case": 14,
            "timeout_seconds_per_call": 75,
            "monetary_cost_ceiling_usd": 0,
        },
        "workflow_version": WORKFLOW_VERSION,
        "policy_version": POLICY_VERSION,
        "coverage": coverage,
        "evaluation_interpretation": {
            "independent_heldout_claim_allowed": True,
            "provenance": "fresh post-repair laboratory captures",
            "independent_heldout_capture_groups": 11,
            "variants_within_one_capture_are_not_independent": True,
            "model_controls": "bounded observation-bundle order only",
            "diagnosis_controls": "trusted pre-registered synthetic-lab policy",
        },
        "retrieval_access": (
            "equivalent explicit UNAVAILABLE result for both workflows; frozen retrieval quality "
            "is retained from the separate v1 comparison"
        ),
        "paid_calls_authorized": False,
        "run_plan_version": RUN_PLAN_VERSION,
    }


def write_freeze(path: Path = FREEZE_PATH) -> dict[str, Any]:
    if path.exists():
        raise FileExistsError("Phase 9 v4 freeze exists; refusing to overwrite it")
    document = freeze_document()
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return document


def verify_freeze(path: Path = FREEZE_PATH) -> dict[str, Any]:
    frozen = json.loads(path.read_text(encoding="utf-8"))
    if frozen.get("freeze_id") != FREEZE_ID:
        raise ValueError("unexpected Phase 9 v4 freeze ID")
    mismatches = []
    for relative, expected in frozen["file_sha256"].items():
        actual = _sha256(ROOT / relative)
        if actual != expected:
            mismatches.append({"path": relative, "expected": expected, "actual": actual})
    current_seal = verify_fixture()
    if current_seal["digest"] != frozen["heldout_seal"]["digest"]:
        mismatches.append({"path": "heldout seal", "expected": "frozen", "actual": "changed"})
    if mismatches:
        raise ValueError(f"Phase 9 v4 freeze verification failed: {mismatches}")
    return {"status": "pass", "freeze_id": FREEZE_ID, "file_count": len(frozen["file_sha256"])}


async def run_agent_shard(output_dir: Path, shard_index: int, shard_count: int) -> dict[str, Any]:
    verify_freeze()
    if shard_count < 1 or not 0 <= shard_index < shard_count:
        raise ValueError("shard index must be zero-based and less than shard count")
    identity = await runtime_identity()
    settings = _settings(Settings())  # type: ignore[call-arg]
    problems = settings.validate_runtime()
    if problems:
        raise ValueError("invalid Phase 9 v4 runtime: " + "; ".join(problems))
    selected = [job for index, job in enumerate(agent_jobs()) if index % shard_count == shard_index]
    await asyncio.to_thread(output_dir.mkdir, parents=True, exist_ok=True)
    path = output_dir / f"agent-part-{shard_index:02d}-of-{shard_count:02d}.jsonl"
    path_exists = await asyncio.to_thread(path.exists)
    previous = await asyncio.to_thread(_jsonl, path) if path_exists else []
    completed = {item["job_id"] for item in previous}
    planner = LocalStructuredV3Model(settings)
    run_count = 0
    with path.open("a", encoding="utf-8") as handle:
        for job in selected:
            if job["job_id"] in completed:
                continue
            case = job["case"]
            try:
                result = (
                    await run_fixed_case(case, settings, source_job_id=job["job_id"])
                    if job["workflow"] == "fixed"
                    else await run_adaptive_case(
                        case,
                        settings,
                        planner,
                        source_job_id=job["job_id"],
                    )
                )
            except Exception as exc:
                result = {
                    "case_id": case["case_id"],
                    "workflow": job["workflow"],
                    "workflow_version": WORKFLOW_VERSION,
                    "policy_version": POLICY_VERSION,
                    "status": "failed",
                    "report_valid": False,
                    "termination_reason": "unhandled_v4_evaluation_error",
                    "error_summaries": [f"{type(exc).__name__}: {exc}"],
                    "evidence_ids": [],
                    "tool_trace": [],
                    "decision_summaries": [],
                    "counters": {
                        "model_calls": 0,
                        "tool_calls": 0,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "estimated_cost_usd": 0,
                        "active_duration_ms": 0,
                    },
                    "report": None,
                }
            record = {
                "schema_version": 1,
                "freeze_id": FREEZE_ID,
                "evaluation_mode": "fresh_post_repair",
                "run_plan_version": RUN_PLAN_VERSION,
                "job_id": job["job_id"],
                "split": job["split"],
                "repeat": job["repeat"],
                "group_id": case["group_id"],
                "provenance_category": case["provenance_category"],
                "snapshot_id": case["snapshot_id"],
                "model": identity,
                "created_at": datetime.now(UTC).isoformat(),
                **result,
            }
            handle.write(_canonical(record) + "\n")
            handle.flush()
            run_count += 1
            print(
                _canonical(
                    {
                        "job": job["job_id"],
                        "status": result["status"],
                        "model_calls": result["counters"].get("model_calls", 0),
                    }
                ),
                flush=True,
            )
    return {
        "status": "complete",
        "path": str(path),
        "assigned": len(selected),
        "newly_run": run_count,
        "total_records": len(_jsonl(path)),
    }


def _load_parts(output_dir: Path) -> list[dict[str, Any]]:
    rows = [item for path in sorted(output_dir.glob("agent-part-*.jsonl")) for item in _jsonl(path)]
    by_job: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row["job_id"] in by_job and _canonical(row) != _canonical(by_job[row["job_id"]]):
            raise ValueError(f"conflicting duplicate agent job: {row['job_id']}")
        by_job[row["job_id"]] = row
    expected = [item["job_id"] for item in agent_jobs()]
    missing = [item for item in expected if item not in by_job]
    if missing:
        raise ValueError(f"Phase 9 v4 evaluation is incomplete: {len(missing)} jobs missing")
    return [by_job[item] for item in expected]


def finalize(output_dir: Path) -> dict[str, Any]:
    freeze = verify_freeze()
    runs = _load_parts(output_dir)
    labels = {
        item["case_id"]: item
        for item in [*_jsonl(DEV_LABEL_PATH), *_jsonl(LABEL_PATH)]
    }
    scores = [score_incident_run(run, labels[run["case_id"]]) for run in runs]
    heldout = {
        workflow: _aggregate_agent(
            [row for row in scores if row["split"] == "heldout" and row["workflow"] == workflow]
        )
        for workflow in WORKFLOWS
    }
    development_repeats = {
        workflow: {
            str(repeat): _aggregate_agent(
                [
                    row
                    for row in scores
                    if row["split"] == "dev"
                    and row["workflow"] == workflow
                    and row["repeat"] == repeat
                ]
            )
            for repeat in range(1, 4)
        }
        for workflow in WORKFLOWS
    }
    adaptive = heldout["adaptive"]
    coverage = json.loads(COVERAGE_PATH.read_text(encoding="utf-8"))
    coverage_percent = float(coverage["totals"]["percent_covered"])
    targets = {
        "diagnosis_top1": (adaptive["top1"]["rate"] or 0) >= 0.75,
        "diagnosis_top3": (adaptive["top3"]["rate"] or 0) >= 0.90,
        "appropriate_abstention": adaptive["appropriate_abstention"]["numerator"] >= 4,
        "false_incidents": adaptive["false_incidents"]["numerator"] <= 1,
        "citation_validity": adaptive["citation_validity"]["rate"] == 1.0,
        "policy_violations": adaptive["policy_violations"] == 0,
        "warm_p95_active_seconds": (
            adaptive["p95_active_duration_ms"] is not None
            and adaptive["p95_active_duration_ms"] < 90_000
        ),
        "supported_claim_rate": None,
        "core_coverage": coverage_percent >= 85,
    }
    result = {
        "schema_version": 1,
        "freeze": freeze,
        "evaluation_mode": "fresh_post_repair",
        "independent_heldout_claim_allowed": True,
        "agent": {
            "fresh_heldout": heldout,
            "consumed_development_repeats": development_repeats,
        },
        "coverage": {
            "percent": coverage_percent,
            "scope": coverage["scope"],
        },
        "targets": targets,
        "gate_status": "pending_manual_review",
        "limitations": [
            "This is a small project-authored laboratory dataset, not production evidence.",
            "Thirty cases share 11 captures; question variants are not independent observations.",
            "The local model controls bounded observation order only; trusted code applies the "
            "pre-registered synthetic-lab diagnosis policy.",
            "Document retrieval is equally unavailable to both v4 agent workflows; retrieval "
            "quality remains a separate frozen v1 result.",
            "Supported factual claim rate requires written review of at least 20 fresh reports.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "aggregate.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with (output_dir / "per-case.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(scores[0]))
        writer.writeheader()
        writer.writerows(scores)
    lines = [
        "# Phase 9 v4 fresh post-repair evaluation",
        "",
        "Status: **PENDING MANUAL REVIEW**.",
        "",
        "| Workflow | Top 1 | Top 3 | Abstention | False incidents | Task completion |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for workflow, metrics in heldout.items():
        lines.append(
            f"| {workflow} | {metrics['top1']['numerator']}/{metrics['top1']['denominator']} | "
            f"{metrics['top3']['numerator']}/{metrics['top3']['denominator']} | "
            f"{metrics['appropriate_abstention']['numerator']}/"
            f"{metrics['appropriate_abstention']['denominator']} | "
            f"{metrics['false_incidents']['numerator']}/"
            f"{metrics['false_incidents']['denominator']} | "
            f"{metrics['task_completion']['numerator']}/"
            f"{metrics['task_completion']['denominator']} |"
        )
    lines.extend(["", "## Automated target status", ""])
    for name, passed in targets.items():
        label = "PENDING" if passed is None else "PASS" if passed else "FAIL"
        lines.append(f"- `{name}`: **{label}**")
    lines.extend(["", "## Limitations", ""])
    limitations = result["limitations"]
    assert isinstance(limitations, list)
    lines.extend(f"- {item}" for item in limitations)
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="IncidentGraph Phase 9 v4 evaluation")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("write-freeze")
    sub.add_parser("print-freeze")
    sub.add_parser("verify-freeze")
    agent = sub.add_parser("run-agent-shard")
    agent.add_argument("--output-dir", type=Path, default=DEFAULT_RUN_DIR)
    agent.add_argument("--shard-index", type=int, required=True)
    agent.add_argument("--shard-count", type=int, required=True)
    report = sub.add_parser("finalize")
    report.add_argument("--output-dir", type=Path, default=DEFAULT_RUN_DIR)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "write-freeze":
        print(json.dumps(write_freeze(), indent=2, sort_keys=True))
        return
    if args.command == "print-freeze":
        print(json.dumps(freeze_document(), indent=2, sort_keys=True))
        return
    if args.command == "verify-freeze":
        print(json.dumps(verify_freeze(), indent=2, sort_keys=True))
        return
    if args.command == "run-agent-shard":
        result = asyncio.run(run_agent_shard(args.output_dir, args.shard_index, args.shard_count))
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    print(json.dumps(finalize(args.output_dir), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
