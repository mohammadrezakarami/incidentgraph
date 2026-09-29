from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

REVIEWED_AT = "2026-09-28T00:00:00Z"
REVIEWER = "AI-assisted semantic review (not independent human validation)"
SOURCE_ARCHIVE_SHA256 = "2345d2b070f26806cdfb96a874eb637e30e381c0562a5829aee08cd2ecbdde09"
REPRODUCED_AGGREGATE_SHA256 = "e9a2cb42e31f3aadbf0111796093084ddc9c3287cddbb08ea5a99541385808ce"
REPRODUCED_PER_CASE_SHA256 = "8a8effb01a46962629a66b55693d325f1989424cb5a50f5aa8194583413c55c7"

SAMPLE_JOB_IDS = [
    f"heldout-r1-adaptive-incident-v3-heldout-{case_number:03d}" for case_number in range(1, 21)
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def render_summary(result: dict[str, Any]) -> str:
    lines = [
        "# Phase 9 v3 fresh post-corpus evaluation",
        "",
        "Status: **FAIL — EVALUATION COMPLETE**.",
        "",
        "The 120-job free-Colab evaluation reproduced byte-for-byte from the returned per-job "
        "records. The written review covers 20 actual adaptive reports and is AI-assisted, not "
        "independent human validation.",
        "",
        "## Fresh held-out comparison",
        "",
        "| Workflow | Top 1 | Top 3 | Abstention | False incidents | Task completion |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for workflow, metrics in result["agent"]["fresh_heldout"].items():
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

    review = result["manual_review"]
    lines.extend(
        [
            "",
            "## Claim-support review",
            "",
            f"- Actual reports reviewed: {review['actual_reports_reviewed']}",
            f"- Supported atomic factual claims: {review['supported_factual_claim_count']}/"
            f"{review['factual_claim_count']} ({review['supported_claim_rate']:.1%})",
            "- Frozen target: at least 95%",
            "- Result: **FAIL**",
            "",
            "## Target status",
            "",
        ]
    )
    for name, status in result["targets"].items():
        lines.append(f"- `{name}`: **{'PASS' if status else 'FAIL'}**")
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in result["limitations"])
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--source-archive", type=Path, required=True)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    source_archive = args.source_archive.resolve()

    if sha256(source_archive) != SOURCE_ARCHIVE_SHA256:
        raise ValueError("source archive does not match the returned Phase 9 v3 archive")

    pre_review_path = output_dir / "aggregate-pre-review.json"
    per_case_path = output_dir / "per-case.csv"
    if sha256(pre_review_path) != REPRODUCED_AGGREGATE_SHA256:
        raise ValueError("pre-review aggregate does not match the reproduced Colab output")
    if sha256(per_case_path) != REPRODUCED_PER_CASE_SHA256:
        raise ValueError("per-case CSV does not match the reproduced Colab output")

    runs: dict[str, dict[str, Any]] = {}
    for path in sorted(output_dir.glob("agent-part-*.jsonl")):
        runs.update({row["job_id"]: row for row in load_jsonl(path)})

    rows: list[dict[str, Any]] = []
    for job_id in SAMPLE_JOB_IDS:
        run = runs[job_id]
        report = run["report"]
        if report is None:
            raise ValueError(f"sampled job has no report: {job_id}")
        if any(
            report[field]
            for field in (
                "observed_symptoms",
                "observed_impact",
                "potential_impact",
                "ranked_hypotheses",
            )
        ):
            raise ValueError(f"unexpected claim-bearing field in {job_id}")

        conclusion = report["summary"]
        if conclusion not in {
            "The available observations are insufficient to identify one supported cause.",
            "No bounded incident signal was established in the available observations.",
        }:
            raise ValueError(f"unexpected summary conclusion in {job_id}")

        rows.append(
            {
                "job_id": job_id,
                "case_id": run["case_id"],
                "workflow": run["workflow"],
                "case_type": "identifiable",
                "report": report,
                "rubric": {
                    "factual_claim_count": 1,
                    "supported_factual_claim_count": 0,
                    "unsupported_claims": [conclusion],
                    "citation_support_notes": (
                        "The report supplies no evidence citation for its only externally "
                        "verifiable conclusion, and the sealed case is answerable. Explicit "
                        "epistemic limitations are excluded from the claim denominator."
                    ),
                    "reviewer": REVIEWER,
                    "reviewed_at": REVIEWED_AT,
                },
            }
        )

    factual = sum(row["rubric"]["factual_claim_count"] for row in rows)
    supported = sum(row["rubric"]["supported_factual_claim_count"] for row in rows)
    rate = supported / factual
    if (len(rows), factual, supported) != (20, 20, 0):
        raise ValueError("unexpected Phase 9 v3 manual-review aggregate")

    review_summary = {
        "schema_version": 1,
        "reviewed_at": REVIEWED_AT,
        "reviewer": REVIEWER,
        "independent_human_validation": False,
        "source_archive_sha256": SOURCE_ARCHIVE_SHA256,
        "reproduced_aggregate_sha256": REPRODUCED_AGGREGATE_SHA256,
        "reproduced_per_case_sha256": REPRODUCED_PER_CASE_SHA256,
        "selection": SAMPLE_JOB_IDS,
        "selection_rule": (
            "case-order sample of the 20 fresh held-out identifiable adaptive reports"
        ),
        "actual_reports_reviewed": len(rows),
        "factual_claim_count": factual,
        "supported_factual_claim_count": supported,
        "supported_claim_rate": rate,
        "target": 0.95,
        "passed": False,
        "method": (
            "Count unique atomic externally verifiable conclusions in summaries, observed "
            "symptoms, observed or potential impact, and ranked-hypothesis mechanism or "
            "explanation fields. Deduplicate summary restatements and exclude recommendations, "
            "schema metadata, and explicit epistemic limitations. A claim passes only when cited "
            "eligible run evidence directly entails it. All sampled reports left the structured "
            "claim fields empty and emitted one uncited generic conclusion."
        ),
    }

    aggregate = json.loads(pre_review_path.read_text(encoding="utf-8"))
    aggregate["manual_review"] = review_summary
    aggregate["targets"]["supported_claim_rate"] = False
    aggregate["gate_status"] = "fail"
    aggregate["limitations"] = [
        item
        for item in aggregate["limitations"]
        if not item.startswith("Supported factual claim rate requires")
    ]
    aggregate["limitations"].extend(
        [
            "The written semantic rubric is AI-assisted and is not independent human validation.",
            "The 20 reviewed adaptive reports contained no cited factual diagnosis; each emitted "
            "only one unsupported generic conclusion.",
        ]
    )

    (output_dir / "manual-review.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )
    (output_dir / "manual-review-summary.json").write_text(
        json.dumps(review_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "aggregate.json").write_text(
        json.dumps(aggregate, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "summary.md").write_text(render_summary(aggregate), encoding="utf-8")

    print(
        json.dumps(
            {
                "gate_status": aggregate["gate_status"],
                "actual_reports_reviewed": len(rows),
                "supported_claims": f"{supported}/{factual}",
                "supported_claim_rate": rate,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
