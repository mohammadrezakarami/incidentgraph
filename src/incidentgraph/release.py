from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
EVALUATION_DIR = ROOT / "artifacts" / "evaluation" / "phase9-v4-fresh"
RESTORE_CONFIRMATION = "RESTORE_INCIDENTGRAPH_APP_DB"

REQUIRED_FILES = (
    "Dockerfile",
    "LICENSE.md",
    "README.md",
    "pyproject.toml",
    "uv.lock",
    "frontend/package-lock.json",
    ".env.example",
    ".gitignore",
    ".dockerignore",
    ".github/workflows/ci.yml",
    ".github/workflows/security.yml",
    ".github/workflows/real-model-evaluation.yml",
    "docs/operations/RELEASE.md",
    "docs/portfolio/FINAL_TECHNICAL_REPORT.md",
    "docs/portfolio/FINAL_READINESS.md",
    "docs/security/THREAT_MODEL.md",
)

REQUIRED_MAKE_TARGETS = (
    "doctor",
    "bootstrap",
    "up",
    "seed",
    "ingest",
    "smoke",
    "scenario",
    "capture",
    "demo",
    "test",
    "test-integration",
    "test-e2e",
    "evaluate-dev",
    "evaluate-test",
    "report",
    "down",
    "test-offline",
    "release-verify",
    "backup-app",
    "restore-app",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def evaluation_report(root: Path = ROOT) -> dict[str, Any]:
    directory = root / "artifacts" / "evaluation" / "phase9-v4-fresh"
    aggregate = json.loads((directory / "aggregate.json").read_text(encoding="utf-8"))
    review = json.loads((directory / "manual-review-summary.json").read_text(encoding="utf-8"))
    parts = sorted(directory.glob("agent-part-*-of-12.jsonl"))
    rows = [
        json.loads(line)
        for part in parts
        for line in part.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    costs = [row.get("counters", {}).get("estimated_cost_usd") for row in rows]
    if any(
        isinstance(cost, bool) or not isinstance(cost, (int, float)) or cost < 0 for cost in costs
    ):
        raise ValueError("evaluation records contain an invalid estimated cost")
    targets = aggregate.get("targets", {})
    return {
        "status": aggregate.get("gate_status"),
        "freeze_id": aggregate.get("freeze", {}).get("freeze_id"),
        "agent_parts": len(parts),
        "agent_records": len(rows),
        "targets_passed": sorted(name for name, passed in targets.items() if passed is True),
        "targets_failed": sorted(name for name, passed in targets.items() if passed is not True),
        "reports_reviewed": review.get("actual_reports_reviewed"),
        "supported_claims": review.get("supported_factual_claim_count"),
        "factual_claims": review.get("factual_claim_count"),
        "paid_cost_usd": sum(costs),
        "limitations": aggregate.get("limitations", []),
    }


def verify_evaluation(root: Path = ROOT) -> dict[str, Any]:
    from incidentgraph.phase9_v4_runner import finalize

    directory = root / "artifacts" / "evaluation" / "phase9-v4-fresh"
    expected_parts = {f"agent-part-{index:02d}-of-12.jsonl" for index in range(12)}
    parts = sorted(directory.glob("agent-part-*-of-12.jsonl"))
    if {part.name for part in parts} != expected_parts:
        raise ValueError("committed evaluation must contain exactly the twelve expected shards")

    by_job: dict[str, dict[str, Any]] = {}
    record_count = 0
    for part in parts:
        for line in part.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record_count += 1
            row = json.loads(line)
            job_id = row.get("job_id")
            if not isinstance(job_id, str) or not job_id:
                raise ValueError(f"evaluation record in {part.name} has no job ID")
            if job_id in by_job and row != by_job[job_id]:
                raise ValueError(f"conflicting duplicate evaluation job: {job_id}")
            by_job[job_id] = row
    if record_count != 120 or len(by_job) != 120:
        raise ValueError(
            f"expected exactly 120 evaluation records and jobs, found "
            f"{record_count} records and {len(by_job)} jobs"
        )

    with tempfile.TemporaryDirectory(prefix="incidentgraph-evaluation-") as temporary:
        replay = Path(temporary)
        for part in parts:
            shutil.copyfile(part, replay / part.name)
        finalize(replay)
        if (replay / "aggregate.json").read_bytes() != (
            directory / "aggregate-pre-review.json"
        ).read_bytes():
            raise ValueError(
                "committed pre-review aggregate does not reproduce from per-job records"
            )
        if (replay / "per-case.csv").read_bytes() != (directory / "per-case.csv").read_bytes():
            raise ValueError("committed per-case table does not reproduce from per-job records")

    review = json.loads((directory / "manual-review-summary.json").read_text(encoding="utf-8"))
    if review.get("reproduced_aggregate_sha256") != _sha256(
        directory / "aggregate-pre-review.json"
    ):
        raise ValueError("manual review references the wrong pre-review aggregate")
    if review.get("reproduced_per_case_sha256") != _sha256(directory / "per-case.csv"):
        raise ValueError("manual review references the wrong per-case table")

    review_rows = [
        json.loads(line)
        for line in (directory / "manual-review.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    selection = review.get("selection")
    if not isinstance(selection, list) or [row.get("job_id") for row in review_rows] != selection:
        raise ValueError("manual-review rows do not match the declared selection")
    factual = 0
    supported = 0
    groups: set[str] = set()
    for row in review_rows:
        job_id = row["job_id"]
        run = by_job.get(job_id)
        if run is None:
            raise ValueError(f"manual review references an unknown job: {job_id}")
        if row.get("report") != run.get("report"):
            raise ValueError(f"manual review report differs from the run record: {job_id}")
        if row.get("case_id") != run.get("case_id") or row.get("group_id") != run.get("group_id"):
            raise ValueError(f"manual review identity differs from the run record: {job_id}")
        rubric = row.get("rubric", {})
        claims = rubric.get("claims")
        if not isinstance(claims, list) or not claims:
            raise ValueError(f"manual review has no claims: {job_id}")
        supported_rows = [claim for claim in claims if claim.get("supported") is True]
        run_evidence = set(run.get("evidence_ids", []))
        if any(
            not isinstance(claim.get("evidence_ids"), list)
            or not claim["evidence_ids"]
            or not set(claim["evidence_ids"]).issubset(run_evidence)
            for claim in claims
        ):
            raise ValueError(f"manual review cites evidence outside its run: {job_id}")
        if rubric.get("factual_claim_count") != len(claims) or rubric.get(
            "supported_factual_claim_count"
        ) != len(supported_rows):
            raise ValueError(f"manual review claim counts are inconsistent: {job_id}")
        factual += len(claims)
        supported += len(supported_rows)
        groups.add(str(row["group_id"]))

    if (
        len(review_rows) != review.get("actual_reports_reviewed")
        or len(groups) != review.get("independent_groups_represented")
        or factual != review.get("factual_claim_count")
        or supported != review.get("supported_factual_claim_count")
        or not review.get("passed")
        or review.get("independent_human_validation") is not False
    ):
        raise ValueError("manual-review summary does not match its rubric rows")
    rate = supported / factual
    target = review.get("target")
    if (
        not isinstance(target, (int, float))
        or review.get("supported_claim_rate") != rate
        or rate < target
    ):
        raise ValueError("manual-review supported-claim rate is invalid")

    aggregate = json.loads((directory / "aggregate.json").read_text(encoding="utf-8"))
    pre_review = json.loads((directory / "aggregate-pre-review.json").read_text(encoding="utf-8"))
    immutable_fields = (
        "agent",
        "coverage",
        "evaluation_mode",
        "freeze",
        "independent_heldout_claim_allowed",
    )
    for key in immutable_fields:
        if aggregate.get(key) != pre_review.get(key):
            raise ValueError(f"post-review aggregate changed frozen automated field: {key}")
    if (
        aggregate.get("manual_review") != review
        or aggregate.get("gate_status") != "pass"
        or not aggregate.get("targets")
        or any(value is not True for value in aggregate["targets"].values())
    ):
        raise ValueError("post-review aggregate is not a complete passing gate")

    report = evaluation_report(root)
    if report["paid_cost_usd"] != 0:
        raise ValueError("committed zero-paid-cost evaluation contains a nonzero estimated cost")
    return {**report, "reproduced_from_records": True}


def _check(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "passed": passed, "detail": detail}


def verify_release(root: Path = ROOT) -> dict[str, Any]:
    from incidentgraph.phase9_v4_runner import verify_freeze

    checks: list[dict[str, Any]] = []
    missing = [item for item in REQUIRED_FILES if not (root / item).is_file()]
    checks.append(
        _check("required_files", not missing, f"missing={missing}" if missing else "present")
    )

    makefile = (root / "Makefile").read_text(encoding="utf-8")
    make_targets = set(re.findall(r"^([A-Za-z0-9][A-Za-z0-9_-]*):", makefile, re.MULTILINE))
    missing_targets = sorted(set(REQUIRED_MAKE_TARGETS) - make_targets)
    checks.append(
        _check(
            "operational_make_targets",
            not missing_targets,
            f"missing={missing_targets}"
            if missing_targets
            else "all documented operations implemented",
        )
    )

    readme = (root / "README.md").read_text(encoding="utf-8")
    missing_commands = [
        f"make {target}" for target in REQUIRED_MAKE_TARGETS if f"make {target}" not in readme
    ]
    checks.append(
        _check(
            "readme_command_parity",
            not missing_commands,
            f"missing={missing_commands}"
            if missing_commands
            else "README names every operational target",
        )
    )

    deployment_files = [root / "Dockerfile", root / "lab.Dockerfile", root / "ops" / "compose.yaml"]
    deployment_text = "\n".join(
        path.read_text(encoding="utf-8") for path in deployment_files if path.is_file()
    )
    remote_images = []
    for line in deployment_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("image:"):
            image = stripped.removeprefix("image:").strip()
            if not image.startswith("incidentgraph-"):
                remote_images.append(image)
    unpinned = [image for image in remote_images if "@sha256:" not in image]
    dockerfile_unpinned = [
        line.strip()
        for path in (root / "Dockerfile", root / "lab.Dockerfile")
        if path.is_file()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("FROM ") and "@sha256:" not in line
    ]
    checks.append(
        _check(
            "container_pins",
            not unpinned and not dockerfile_unpinned and ":latest" not in deployment_text,
            f"unpinned={unpinned + dockerfile_unpinned}"
            if unpinned or dockerfile_unpinned
            else "remote images and bases use immutable digests",
        )
    )

    dockerignore = (root / ".dockerignore").read_text(encoding="utf-8")
    checks.append(
        _check(
            "private_evaluator_excluded",
            "data/evaluator" in dockerignore,
            "data/evaluator excluded from image context",
        )
    )

    git = subprocess.run(
        ["/usr/bin/git", "ls-files", "--error-unmatch", ".env"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    checks.append(_check("local_env_untracked", git.returncode != 0, ".env is not tracked"))

    try:
        freeze = verify_freeze(root / "config" / "phase9-v4-fresh-freeze.json")
        freeze_passed = freeze.get("status") == "pass" and freeze.get("file_count") == 28
        freeze_detail = f"freeze_id={freeze.get('freeze_id')}, files={freeze.get('file_count')}"
    except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        freeze_passed = False
        freeze_detail = f"invalid Phase 9 v4 source/data seal: {exc}"
    checks.append(_check("phase9_v4_freeze", freeze_passed, freeze_detail))

    try:
        report = verify_evaluation(root)
        evaluation_passed = (
            report["status"] == "pass"
            and report["agent_parts"] == 12
            and report["agent_records"] == 120
            and not report["targets_failed"]
            and report["reports_reviewed"] >= 20
            and report["paid_cost_usd"] == 0
        )
        evaluation_detail = (
            f"status={report['status']}, jobs={report['agent_records']}, "
            f"reviewed={report['reports_reviewed']}, paid_usd={report['paid_cost_usd']}"
        )
    except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        evaluation_passed = False
        evaluation_detail = f"invalid committed evaluation evidence: {exc}"
    checks.append(_check("frozen_evaluation_evidence", evaluation_passed, evaluation_detail))

    release_doc = root / "docs" / "operations" / "RELEASE.md"
    release_text = release_doc.read_text(encoding="utf-8") if release_doc.is_file() else ""
    operations_topics = (
        "Clean-clone verification",
        "Resource profiles",
        "Backup and restore",
        "Safe shutdown",
        "Troubleshooting",
        "Known limitations",
        "Offline deterministic replay",
    )
    missing_topics = [topic for topic in operations_topics if topic not in release_text]
    checks.append(
        _check(
            "operations_runbook",
            not missing_topics,
            f"missing={missing_topics}"
            if missing_topics
            else "required operational topics documented",
        )
    )

    failures = [item for item in checks if not item["passed"]]
    return {
        "schema_version": 1,
        "status": "pass" if not failures else "fail",
        "checked_at": datetime.now(UTC).isoformat(),
        "checks": checks,
        "failure_count": len(failures),
    }


def _compose_prefix(project_name: str) -> list[str]:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,62}", project_name):
        raise ValueError(
            "Compose project name must use lowercase letters, digits, '.', '_', or '-'"
        )
    return [
        "docker",
        "compose",
        "-p",
        project_name,
        "-f",
        "ops/compose.yaml",
        "--env-file",
        ".env",
    ]


def backup_command(project_name: str) -> list[str]:
    return [
        *_compose_prefix(project_name),
        "exec",
        "-T",
        "app-db",
        "pg_dump",
        "-U",
        "incidentgraph",
        "-d",
        "incidentgraph",
        "--format=custom",
        "--no-owner",
        "--no-privileges",
    ]


def restore_command(project_name: str, *, list_only: bool = False) -> list[str]:
    command = [
        *_compose_prefix(project_name),
        "exec",
        "-T",
        "app-db",
        "pg_restore",
    ]
    if list_only:
        return [*command, "--list"]
    return [
        *command,
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-privileges",
        "-U",
        "incidentgraph",
        "-d",
        "incidentgraph",
    ]


def backup_app(output: Path, project_name: str) -> dict[str, Any]:
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing backup: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.partial")
    try:
        with temporary.open("wb") as handle:
            subprocess.run(  # noqa: S603 - fixed argv, validated project name, no shell
                backup_command(project_name), cwd=ROOT, stdout=handle, check=True
            )
        if temporary.stat().st_size == 0:
            raise RuntimeError("pg_dump produced an empty backup")
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    manifest = {
        "schema_version": 1,
        "kind": "incidentgraph-app-postgresql-custom-dump",
        "created_at": datetime.now(UTC).isoformat(),
        "file": output.name,
        "bytes": output.stat().st_size,
        "sha256": _sha256(output),
        "compose_project": project_name,
    }
    manifest_path = output.with_suffix(f"{output.suffix}.sha256.json")
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {**manifest, "manifest": str(manifest_path)}


def restore_app(input_path: Path, project_name: str, confirmation: str) -> dict[str, Any]:
    if confirmation != RESTORE_CONFIRMATION:
        raise ValueError(f"restore requires --confirm {RESTORE_CONFIRMATION}")
    input_path = input_path.resolve()
    manifest_path = input_path.with_suffix(f"{input_path.suffix}.sha256.json")
    if not input_path.is_file() or not manifest_path.is_file():
        raise FileNotFoundError("backup and its .sha256.json manifest are both required")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    actual = _sha256(input_path)
    if actual != manifest.get("sha256"):
        raise ValueError("backup checksum does not match its manifest")
    for command in (restore_command(project_name, list_only=True), restore_command(project_name)):
        with input_path.open("rb") as handle:
            subprocess.run(  # noqa: S603 - fixed argv, validated project name, no shell
                command, cwd=ROOT, stdin=handle, check=True
            )
    return {
        "status": "restored",
        "file": str(input_path),
        "sha256": actual,
        "compose_project": project_name,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="incidentgraph-release")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("verify")
    sub.add_parser("verify-evaluation")
    sub.add_parser("report")
    backup = sub.add_parser("backup-app")
    backup.add_argument("--output", type=Path, required=True)
    backup.add_argument("--project-name", default="incidentgraph")
    restore = sub.add_parser("restore-app")
    restore.add_argument("--input", type=Path, required=True)
    restore.add_argument("--project-name", default="incidentgraph")
    restore.add_argument("--confirm", default="")
    return parser


def main() -> None:
    args = _parser().parse_args()
    try:
        if args.command == "verify":
            result = verify_release()
        elif args.command == "verify-evaluation":
            result = verify_evaluation()
        elif args.command == "report":
            result = evaluation_report()
        elif args.command == "backup-app":
            result = backup_app(args.output, args.project_name)
        else:
            result = restore_app(args.input, args.project_name, args.confirm)
    except (
        FileNotFoundError,
        FileExistsError,
        RuntimeError,
        ValueError,
        subprocess.CalledProcessError,
    ) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2), file=sys.stderr)
        raise SystemExit(2) from exc
    print(json.dumps(result, indent=2, sort_keys=True))
    if result.get("status") == "fail":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
