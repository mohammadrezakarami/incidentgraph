# ruff: noqa: E501
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

REVIEWED_AT = "2026-09-25T00:00:00Z"
REVIEWER = "AI-assisted semantic review (not independent human validation)"
SOURCE_ARCHIVE_SHA256 = "34b1413c93e92733381b52c1de4a03f28ede626d0e4d09e2fc358ab8ceafbc06"
REPRODUCED_AGGREGATE_SHA256 = "cdf77609bf2712484d21947cadbc95f92f93eced3a64260d49313349e66ff342"
REPRODUCED_PER_CASE_SHA256 = "bfcf14b5b105964c3b67b009ae11fb9c757aeedb22cbc01b408a95e72e137653"


def review(
    factual: int,
    supported: int,
    unsupported: list[str] | None = None,
    note: str = "",
) -> dict[str, Any]:
    unsupported = unsupported or []
    if factual - supported != len(unsupported):
        raise ValueError("each unsupported atomic claim must be listed")
    return {
        "factual_claim_count": factual,
        "supported_factual_claim_count": supported,
        "unsupported_claims": unsupported,
        "citation_support_notes": note,
        "reviewer": REVIEWER,
        "reviewed_at": REVIEWED_AT,
    }


REVIEWS: dict[str, dict[str, Any]] = {
    "heldout-r1-adaptive-incident-heldout-001": review(
        2,
        2,
        note="Both bounded collection claims resolve directly to the cited topology and metric records.",
    ),
    "heldout-r1-adaptive-incident-heldout-002": review(
        4,
        1,
        [
            "The report labels the 1.999–6.003 requests/second series as error rate, but the cited series is outcome=success.",
            "Separate invalid tool attempts do not make the successfully returned bounded metric untrustworthy.",
            "No evidence links service-level fluctuation causally to an unvalidated query execution.",
        ],
        "The cited series supports variability in successful dependency requests only.",
    ),
    "heldout-r1-adaptive-incident-heldout-003": review(
        1, 1, note="The cited record is a lab metric returned by the error-rate query template."
    ),
    "heldout-r1-adaptive-incident-heldout-004": review(
        3,
        3,
        note="All three conservative collection statements match their cited metric or topology result.",
    ),
    "heldout-r1-adaptive-incident-heldout-005": review(
        5,
        1,
        [
            "The report calls a checkout-to-payments outcome=success series an error-rate drop from about 2.0 to zero.",
            "A falling success series does not establish a resolved error or recovery condition.",
            "The uncited trace does not establish that no user-facing symptom or degradation was reported.",
            "Topology adjacency does not establish that the payments dependency was the resolved mechanism.",
        ],
        "The captured topology directly supports only the checkout-to-payments dependency claim.",
    ),
    "heldout-r1-adaptive-incident-heldout-006": review(
        3,
        3,
        note="The metric, latency, and topology collection claims each resolve to the cited records.",
    ),
    "heldout-r1-adaptive-incident-heldout-007": review(
        2,
        2,
        note="Both conservative collection statements match the cited metric and topology records.",
    ),
    "heldout-r1-adaptive-incident-heldout-008": review(
        2,
        2,
        note="Both conservative collection statements match the cited metric and topology records.",
    ),
    "heldout-r1-adaptive-incident-heldout-009": review(
        4,
        2,
        [
            "A dependency edge plus an elevated error series does not by itself establish a causal chain.",
            "The two records come from one captured scenario and do not independently validate the proposed mechanism.",
        ],
        "The cited records support an elevated gateway-to-checkout error series and the dependency edge, but not causality.",
    ),
    "heldout-r1-adaptive-incident-heldout-010": review(
        5,
        1,
        [
            "Calling the observed rate high requires a baseline or threshold that was not cited.",
            "The cited gateway-side rate does not support user-facing transaction degradation.",
            "The cited gateway-side rate does not establish a checkout-service failure as the cause.",
            "The report's absence-of-topology assertion is uncited and the workflow did not query topology.",
        ],
        "The cited metric directly supports only the numeric maximum of about 3.0 error requests/second.",
    ),
    "heldout-r1-adaptive-incident-heldout-011": review(
        2,
        1,
        [
            "A varying dependency error series alone does not establish service-level degradation.",
        ],
        "The cited metric supports the observed 0.0–3.0 requests/second error-rate variation.",
    ),
    "heldout-r1-adaptive-incident-heldout-012": review(
        3,
        1,
        [
            "Service-context metadata does not establish that no operational symptoms occurred.",
            "Configured topology metadata does not establish that the service was operational or healthy.",
        ],
        "The context record supports that svc-payments is configured and present in the lab topology only.",
    ),
    "heldout-r1-adaptive-incident-heldout-013": review(
        2,
        1,
        [
            "The cited topology record does not itself support the uncited claim that no metrics were available.",
        ],
        "The topology record supports reachability through checkout and gateway.",
    ),
    "heldout-r1-adaptive-incident-heldout-014": review(
        2,
        1,
        [
            "The cited topology record does not itself support the uncited claim that no metric telemetry exists.",
        ],
        "The cited topology directly supports the gateway-to-checkout-to-payments dependency chain.",
    ),
    "heldout-r1-adaptive-incident-heldout-015": review(
        3,
        3,
        note="The topology, metric, and log collection claims each resolve to their cited records.",
    ),
    "heldout-r1-adaptive-incident-heldout-016": review(
        7,
        3,
        [
            "The word elevated requires a baseline or threshold not present in the cited latency record.",
            "The cited route latency does not establish degraded user experience.",
            "Checkout-route latency is not evidence that the payments dependency caused processing delay.",
            "The available metric records do not establish processing delay rather than failure.",
        ],
        "The records support p95 near 0.2308 seconds, zero payments-dependency errors, and high successful request rate.",
    ),
    "heldout-r1-adaptive-incident-heldout-017": review(
        1,
        1,
        note="The conservative metric-collection statement resolves to the cited bounded record.",
    ),
    "heldout-r1-adaptive-incident-heldout-018": review(
        1,
        1,
        note="The conservative topology-collection statement resolves to the cited context record.",
    ),
    "heldout-r1-adaptive-incident-heldout-019": review(
        3,
        1,
        [
            "Topology metadata cannot establish absence of performance degradation or service failure.",
            "Missing telemetry is not a causal mechanism for performance degradation.",
        ],
        "The cited record supports only the current svc-payments topology metadata.",
    ),
    "heldout-r1-adaptive-incident-heldout-020": review(
        2,
        1,
        [
            "The cited dependency record does not itself support the uncited claim that no metric telemetry exists.",
        ],
        "The cited topology directly supports the checkout-to-payments dependency flow.",
    ),
}

SUPPLEMENTAL_JOB_IDS = [
    f"heldout-r1-adaptive-incident-heldout-{case_number:03d}" for case_number in range(11, 21)
]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_summary(result: dict[str, Any]) -> str:
    lines = [
        "# Phase 9 frozen evaluation",
        "",
        "Status: **FAIL — evaluation completed**.",
        "",
        "All automated aggregates reproduce byte-for-byte from the 120 per-case records. The "
        "written claim-support review covers 20 actual reports; it is AI-assisted and is not "
        "presented as independent human validation.",
        "",
        "## Held-out agent comparison",
        "",
        "| Workflow | Top 1 | Top 3 | Abstention | False incidents | Task completion |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for workflow, metrics in result["agent"]["heldout"].items():
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
    review_result = result["manual_review"]
    lines.extend(
        [
            "",
            "## Claim-support review",
            "",
            f"- Actual reports reviewed: {review_result['actual_reports_reviewed']}",
            f"- Supported atomic factual claims: {review_result['supported_factual_claim_count']}/"
            f"{review_result['factual_claim_count']} "
            f"({review_result['supported_claim_rate']:.1%})",
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
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()

    aggregate_path = output_dir / "aggregate.json"
    per_case_path = output_dir / "per-case.csv"
    if sha256(aggregate_path) != REPRODUCED_AGGREGATE_SHA256:
        raise ValueError("aggregate.json does not match the independently reproduced Colab output")
    if sha256(per_case_path) != REPRODUCED_PER_CASE_SHA256:
        raise ValueError("per-case.csv does not match the independently reproduced Colab output")

    rows = load_jsonl(output_dir / "manual-review.jsonl")
    if len(rows) != 20:
        raise ValueError("expected the frozen evaluator's 20-row review template")
    null_reports = sum(row.get("report") is None for row in rows)
    if null_reports != 10:
        raise ValueError("expected 10 null fixed-workflow reports in the generated template")

    runs: dict[str, dict[str, Any]] = {}
    for path in sorted(output_dir.glob("agent-part-*.jsonl")):
        runs.update({row["job_id"]: row for row in load_jsonl(path)})
    with per_case_path.open(newline="", encoding="utf-8") as handle:
        case_types = {row["case_id"]: row["case_type"] for row in csv.DictReader(handle)}

    for job_id in SUPPLEMENTAL_JOB_IDS:
        run = runs[job_id]
        rows.append(
            {
                "job_id": job_id,
                "case_id": run["case_id"],
                "workflow": run["workflow"],
                "case_type": case_types[run["case_id"]],
                "report": run["report"],
                "tool_trace": run["tool_trace"],
                "rubric": {},
            }
        )

    actual_report_count = 0
    for row in rows:
        if row.get("report") is None:
            row["rubric"] = review(
                0,
                0,
                note="No report was produced; this generated template row is retained but excluded from the 20-report denominator.",
            )
            continue
        actual_report_count += 1
        try:
            row["rubric"] = REVIEWS[row["job_id"]]
        except KeyError as error:
            raise ValueError(f"missing written review for {row['job_id']}") from error

    if actual_report_count != 20:
        raise ValueError(f"expected 20 actual reports, found {actual_report_count}")
    actual_job_ids = {row["job_id"] for row in rows if row.get("report") is not None}
    if actual_job_ids != set(REVIEWS):
        raise ValueError("reviewed actual-report sample does not match the frozen mapping")

    factual = sum(row["rubric"]["factual_claim_count"] for row in rows)
    supported = sum(row["rubric"]["supported_factual_claim_count"] for row in rows)
    rate = supported / factual
    target = 0.95
    passed = rate >= target
    if (factual, supported) != (57, 32):
        raise ValueError("unexpected manual-review aggregate")

    review_summary = {
        "schema_version": 1,
        "reviewed_at": REVIEWED_AT,
        "reviewer": REVIEWER,
        "independent_human_validation": False,
        "source_archive_sha256": SOURCE_ARCHIVE_SHA256,
        "reproduced_aggregate_sha256": REPRODUCED_AGGREGATE_SHA256,
        "reproduced_per_case_sha256": REPRODUCED_PER_CASE_SHA256,
        "generated_template_rows": 20,
        "generated_template_null_reports": null_reports,
        "supplemental_selection": SUPPLEMENTAL_JOB_IDS,
        "rubric_rows": len(rows),
        "actual_reports_reviewed": actual_report_count,
        "factual_claim_count": factual,
        "supported_factual_claim_count": supported,
        "supported_claim_rate": rate,
        "target": target,
        "passed": passed,
        "method": (
            "Count unique atomic externally verifiable claims in observed symptoms, observed or "
            "potential impact, and ranked-hypothesis mechanism/explanation fields. Deduplicate "
            "restatements in summaries. Exclude recommendations, schema metadata, and explicit "
            "epistemic limitations. A claim passes only when cited eligible run evidence directly "
            "entails it; topology adjacency is not causality, a success series is not an error "
            "series, and qualitative elevation requires a cited baseline or threshold."
        ),
    }

    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    aggregate["manual_review"] = review_summary
    aggregate["targets"]["supported_claim_rate"] = passed
    aggregate["gate_status"] = "pass" if all(aggregate["targets"].values()) else "fail"
    aggregate["limitations"] = [
        item
        for item in aggregate["limitations"]
        if not item.startswith("Supported factual claim rate remains pending")
    ]
    aggregate["limitations"].append(
        "The written semantic rubric is AI-assisted and is not independent human validation."
    )

    manual_path = output_dir / "manual-review.jsonl"
    manual_path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )
    (output_dir / "manual-review-summary.json").write_text(
        json.dumps(review_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    aggregate_path.write_text(
        json.dumps(aggregate, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "summary.md").write_text(render_summary(aggregate), encoding="utf-8")

    print(
        json.dumps(
            {
                "gate_status": aggregate["gate_status"],
                "actual_reports_reviewed": actual_report_count,
                "supported_claims": f"{supported}/{factual}",
                "supported_claim_rate": rate,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
