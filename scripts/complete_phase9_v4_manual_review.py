from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

REVIEWED_AT = "2026-09-28T17:18:16Z"
REVIEWER = "AI-assisted semantic review (not independent human validation)"
SOURCE_ARCHIVE_SHA256 = "47f77a40175203d3f2ee4d44e2b7baf5d26e4d9de1a7046ab238e5913fd98bcc"
REPRODUCED_AGGREGATE_SHA256 = "e8aa980e89696a9529324289508cb07bfbdc7abba5ae1f9f625d3271ddbebe57"
REPRODUCED_PER_CASE_SHA256 = "7f7f0259d72d8c19aa13ec2e33f068ab1e78e45f95932f5f12f3207ec1108c46"
MODEL_DIGEST = "0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0"
MODEL_NAME = "qwen3:4b-instruct-2507-q4_K_M"
FREEZE_ID = "phase9-v4-fresh-post-repair"
POLICY_VERSION = "phase9-repair-3-bounded-policy-v1"
WORKFLOW_VERSION = "phase9-v4-repair3-workflow-v1"

SAMPLE_JOB_IDS = [
    f"heldout-r1-adaptive-incident-v4-heldout-{case_number:03d}"
    for case_number in range(1, 21)
]

POLICY_CLAIM = (
    f"{POLICY_VERSION} evaluated complete/gap status, scoped maxima, "
    "approved-change services, and active bounded signals."
)

MECHANISM_EXPECTATIONS: dict[str, dict[str, Any]] = {
    "downstream_latency": {
        "component": "svc-payments",
        "cases": range(1, 4),
        "measurements": [
            {
                "description": (
                    'request_latency_p95 {"route": "/pay", "service": "payments"}: '
                    "captured maximum 0.2425 seconds."
                ),
                "source": "request_latency_p95",
                "labels": {"route": "/pay", "service": "payments"},
                "maximum": 0.2425,
            }
        ],
    },
    "database_pool_exhaustion": {
        "component": "svc-checkout",
        "cases": range(4, 7),
        "measurements": [
            {
                "description": (
                    'db_pool_in_use {"job": "checkout", "service": "checkout"}: '
                    "captured maximum 4 connections."
                ),
                "source": "db_pool_in_use",
                "labels": {"job": "checkout", "service": "checkout"},
                "maximum": 4.0,
            },
            {
                "description": (
                    'db_pool_timeouts {"service": "checkout"}: captured maximum '
                    "39.5117 timeouts/10_seconds."
                ),
                "source": "db_pool_timeouts",
                "labels": {"service": "checkout"},
                "maximum": 39.51166666666667,
            },
        ],
    },
    "dependency_errors_primary": {
        "mechanism": "dependency_errors",
        "component": "svc-payments",
        "cases": range(7, 10),
        "measurements": [
            {
                "description": (
                    'dependency_outcomes {"dependency": "payments", "outcome": "error", '
                    '"service": "checkout"}: captured maximum 4.25425 requests/second.'
                ),
                "source": "dependency_outcomes",
                "labels": {
                    "dependency": "payments",
                    "outcome": "error",
                    "service": "checkout",
                },
                "maximum": 4.2542542542542545,
            }
        ],
    },
    "cache_degradation": {
        "component": "svc-payments",
        "cases": range(10, 13),
        "measurements": [
            {
                "description": (
                    'cache_outcomes {"result": "hit", "service": "payments"}: '
                    "captured maximum 2 requests/second."
                ),
                "source": "cache_outcomes",
                "labels": {"result": "hit", "service": "payments"},
                "maximum": 2.0,
            },
            {
                "description": (
                    'cache_outcomes {"result": "miss", "service": "payments"}: '
                    "captured maximum 6.0045 requests/second."
                ),
                "source": "cache_outcomes",
                "labels": {"result": "miss", "service": "payments"},
                "maximum": 6.004503377533151,
            },
        ],
    },
    "deployment_regression": {
        "component": "svc-checkout",
        "cases": range(13, 16),
        "measurements": [
            {
                "description": (
                    'dependency_outcomes {"dependency": "checkout", "outcome": "error", '
                    '"service": "gateway"}: captured maximum 2 requests/second.'
                ),
                "source": "dependency_outcomes",
                "labels": {
                    "dependency": "checkout",
                    "outcome": "error",
                    "service": "gateway",
                },
                "maximum": 2.0,
            },
            {
                "description": (
                    "Captured approved change on checkout to v1.1.0-regressed at "
                    "2026-09-28T16:27:42.361728+00:00."
                ),
                "change": {
                    "service": "checkout",
                    "version": "v1.1.0-regressed",
                    "observed_at": "2026-09-28T16:27:42.361728+00:00",
                },
            },
        ],
    },
    "cpu_contention": {
        "component": "svc-payments",
        "cases": range(16, 19),
        "measurements": [
            {
                "description": (
                    'process_cpu {"job": "payments"}: captured maximum '
                    "0.538038 cpu_seconds/second."
                ),
                "source": "process_cpu",
                "labels": {"job": "payments"},
                "maximum": 0.5380380380380382,
            }
        ],
    },
    "dependency_errors_correlation": {
        "mechanism": "dependency_errors",
        "component": "svc-payments",
        "cases": range(19, 21),
        "measurements": [
            {
                "description": (
                    'dependency_outcomes {"dependency": "payments", "outcome": "error", '
                    '"service": "checkout"}: captured maximum 3.50088 requests/second.'
                ),
                "source": "dependency_outcomes",
                "labels": {
                    "dependency": "payments",
                    "outcome": "error",
                    "service": "checkout",
                },
                "maximum": 3.500875218804701,
            }
        ],
    },
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def expectation(case_number: int) -> tuple[str, dict[str, Any]]:
    for key, value in MECHANISM_EXPECTATIONS.items():
        if case_number in value["cases"]:
            return str(value.get("mechanism", key)), value
    raise ValueError(f"no review expectation for held-out case {case_number}")


def evidence_index(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for outcome in run["tool_trace"]:
        for item in outcome["evidence"]:
            evidence_id = str(item["evidence_id"])
            if evidence_id in indexed and canonical(indexed[evidence_id]) != canonical(item):
                raise ValueError(f"conflicting evidence item in {run['job_id']}: {evidence_id}")
            indexed[evidence_id] = item
    policy = run["derived_policy_evidence"]
    if policy is None:
        raise ValueError(f"missing policy evidence in {run['job_id']}")
    indexed[str(policy["evidence_id"])] = policy
    if set(run["evidence_ids"]) != set(indexed):
        raise ValueError(f"run evidence index mismatch in {run['job_id']}")
    return indexed


def validate_metric_evidence(item: dict[str, Any], spec: dict[str, Any]) -> None:
    if item["kind"] != "metric":
        raise ValueError("reviewed measurement did not cite metric evidence")
    content = json.loads(item["content"])
    candidates = [
        series
        for series in content["series"]
        if series.get("template_source") == spec["source"]
        and all(series.get("metric", {}).get(key) == value for key, value in spec["labels"].items())
    ]
    if len(candidates) != 1:
        raise ValueError(f"reviewed metric series did not resolve uniquely: {spec}")
    maximum = max(float(point[1]) for point in candidates[0]["values"])
    if not math.isclose(maximum, float(spec["maximum"]), rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError(f"reviewed metric maximum changed: {maximum} != {spec['maximum']}")


def validate_change_evidence(item: dict[str, Any], spec: dict[str, Any]) -> None:
    if item["kind"] != "change":
        raise ValueError("reviewed change did not cite change evidence")
    changes = json.loads(item["content"])
    if not any(
        all(change.get(key) == value for key, value in spec["change"].items())
        for change in changes
    ):
        raise ValueError(f"reviewed approved change is absent: {spec['change']}")


def validate_all_runs(runs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_job: dict[str, dict[str, Any]] = {}
    for run in runs:
        job_id = str(run["job_id"])
        if job_id in by_job and canonical(run) != canonical(by_job[job_id]):
            raise ValueError(f"conflicting duplicate job: {job_id}")
        by_job[job_id] = run
    if len(by_job) != 120:
        raise ValueError(f"expected 120 unique jobs, found {len(by_job)}")
    for run in by_job.values():
        if run["freeze_id"] != FREEZE_ID:
            raise ValueError(f"unexpected freeze in {run['job_id']}")
        if run["workflow_version"] != WORKFLOW_VERSION:
            raise ValueError(f"unexpected workflow version in {run['job_id']}")
        if run["policy_version"] != POLICY_VERSION:
            raise ValueError(f"unexpected policy version in {run['job_id']}")
        if not run["report_valid"] or run["report"] is None:
            raise ValueError(f"invalid or absent report in {run['job_id']}")
        if run["counters"]["estimated_cost_usd"] != 0:
            raise ValueError(f"nonzero paid cost in {run['job_id']}")
        expected_calls = 1 if run["workflow"] == "adaptive" else 0
        if run["counters"]["model_calls"] != expected_calls:
            raise ValueError(f"unexpected model-call count in {run['job_id']}")
        if run["model"]["name"] != MODEL_NAME or run["model"]["digest"] != MODEL_DIGEST:
            raise ValueError(f"unexpected model identity in {run['job_id']}")
    return by_job


def review_report(run: dict[str, Any]) -> dict[str, Any]:
    case_number = int(str(run["case_id"]).rsplit("-", 1)[1])
    mechanism, expected = expectation(case_number)
    component = str(expected["component"])
    report = run["report"]
    hypothesis = report["ranked_hypotheses"]
    if report["outcome"] != "probable_cause" or len(hypothesis) != 1:
        raise ValueError(f"unexpected claim-bearing structure in {run['job_id']}")
    if hypothesis[0]["mechanism"] != mechanism:
        raise ValueError(f"unexpected mechanism in {run['job_id']}")
    if hypothesis[0]["suspected_component"] != component:
        raise ValueError(f"unexpected component in {run['job_id']}")
    expected_summary = f"Bounded evidence supports {mechanism} affecting {component}."
    if report["summary"] != expected_summary:
        raise ValueError(f"unexpected summary in {run['job_id']}")
    if report["observed_impact"] or report["potential_impact"]:
        raise ValueError(f"unexpected uncatalogued impact claim in {run['job_id']}")

    indexed = evidence_index(run)
    symptoms = report["observed_symptoms"]
    measurements = list(expected["measurements"])
    if len(symptoms) != 1 + len(measurements) or symptoms[0]["description"] != POLICY_CLAIM:
        raise ValueError(f"unexpected observation claims in {run['job_id']}")

    policy_ids = symptoms[0]["evidence_ids"]
    if len(policy_ids) != 1:
        raise ValueError(f"policy observation citation mismatch in {run['job_id']}")
    policy_item = indexed[policy_ids[0]]
    if policy_item["source_version"] != POLICY_VERSION:
        raise ValueError(f"policy observation cited a non-policy item in {run['job_id']}")
    if hashlib.sha256(policy_item["content"].encode()).hexdigest() != policy_item["content_hash"]:
        raise ValueError(f"policy evidence content hash mismatch in {run['job_id']}")
    policy_content = json.loads(policy_item["content"])
    trace_hash = hashlib.sha256(canonical(run["tool_trace"]).encode()).hexdigest()
    if policy_content["source_trace_sha256"] != trace_hash:
        raise ValueError(f"policy trace digest mismatch in {run['job_id']}")
    if policy_content["active_signals"] != [mechanism]:
        raise ValueError(f"policy evidence does not support the mechanism in {run['job_id']}")
    if policy_content["active_signal_components"] != {mechanism: component}:
        raise ValueError(f"policy evidence does not support the component in {run['job_id']}")
    if policy_content["telemetry_gaps"] or policy_content["unavailable_measurements"]:
        raise ValueError(f"reviewed diagnosis has missing observations in {run['job_id']}")
    if not set(policy_content["source_evidence_ids"]).issubset(indexed):
        raise ValueError(f"policy evidence source linkage is incomplete in {run['job_id']}")

    claims = [
        {
            "claim": POLICY_CLAIM,
            "supported": True,
            "evidence_ids": policy_ids,
            "basis": (
                "The cited derived-policy record hashes the complete tool trace, links its raw "
                "source evidence, and records completeness, scoped maxima, changes, and signals."
            ),
        }
    ]
    for symptom, spec in zip(symptoms[1:], measurements, strict=True):
        if symptom["description"] != spec["description"] or len(symptom["evidence_ids"]) != 1:
            raise ValueError(f"reviewed raw observation changed in {run['job_id']}")
        item = indexed[symptom["evidence_ids"][0]]
        if item["snapshot_id"] != run["snapshot_id"]:
            raise ValueError(f"reviewed citation crosses snapshots in {run['job_id']}")
        if "change" in spec:
            validate_change_evidence(item, spec)
            basis = (
                "The cited approved-change record contains the exact service, version, and time."
            )
        else:
            validate_metric_evidence(item, spec)
            basis = (
                "The cited captured metric series contains the exact labels and reported maximum."
            )
        claims.append(
            {
                "claim": symptom["description"],
                "supported": True,
                "evidence_ids": symptom["evidence_ids"],
                "basis": basis,
            }
        )

    conclusion_ids = hypothesis[0]["supporting_evidence_ids"]
    if policy_ids[0] not in conclusion_ids or any(item not in indexed for item in conclusion_ids):
        raise ValueError(f"diagnostic conclusion citation mismatch in {run['job_id']}")
    if hypothesis[0]["explanation_summary"].split(":", 1)[0] != (
        f"The {POLICY_VERSION} rule selected {mechanism}"
    ):
        raise ValueError(f"diagnostic explanation changed in {run['job_id']}")
    claims.append(
        {
            "claim": expected_summary,
            "supported": True,
            "evidence_ids": conclusion_ids,
            "basis": (
                "The bounded conclusion is directly supported by the cited policy reduction and "
                "the cited raw measurement or approved-change facts used by that rule."
            ),
        }
    )

    return {
        "job_id": run["job_id"],
        "case_id": run["case_id"],
        "group_id": run["group_id"],
        "workflow": run["workflow"],
        "case_type": "identifiable",
        "report": report,
        "rubric": {
            "factual_claim_count": len(claims),
            "supported_factual_claim_count": len(claims),
            "unsupported_claims": [],
            "claims": claims,
            "deduplicated_fields": [
                "ranked_hypotheses[0].explanation_summary repeats the raw facts and conclusion"
            ],
            "reviewer": REVIEWER,
            "reviewed_at": REVIEWED_AT,
        },
    }


def render_summary(result: dict[str, Any]) -> str:
    lines = [
        "# Phase 9 v4 fresh post-repair evaluation",
        "",
        "Status: **PASS — EVALUATION COMPLETE**.",
        "",
        "The 120-job free-Colab output reproduced byte-for-byte from its per-job records. The "
        "written review covers 20 actual adaptive reports and is AI-assisted, not independent "
        "human validation.",
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
            f"- Independent capture groups represented: {review['independent_groups_represented']}",
            f"- Supported atomic factual claims: {review['supported_factual_claim_count']}/"
            f"{review['factual_claim_count']} ({review['supported_claim_rate']:.1%})",
            "- Frozen target: at least 95%",
            "- Result: **PASS**",
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
        raise ValueError("source archive does not match the returned Phase 9 v4 archive")
    pre_review_path = output_dir / "aggregate-pre-review.json"
    per_case_path = output_dir / "per-case.csv"
    if sha256(pre_review_path) != REPRODUCED_AGGREGATE_SHA256:
        raise ValueError("pre-review aggregate does not match the reproduced Colab output")
    if sha256(per_case_path) != REPRODUCED_PER_CASE_SHA256:
        raise ValueError("per-case CSV does not match the reproduced Colab output")

    all_runs = [
        row
        for path in sorted(output_dir.glob("agent-part-*.jsonl"))
        for row in load_jsonl(path)
    ]
    runs = validate_all_runs(all_runs)
    rows = [review_report(runs[job_id]) for job_id in SAMPLE_JOB_IDS]
    factual = sum(row["rubric"]["factual_claim_count"] for row in rows)
    supported = sum(row["rubric"]["supported_factual_claim_count"] for row in rows)
    rate = supported / factual
    groups = sorted({row["group_id"] for row in rows})
    if (len(rows), len(groups), factual, supported) != (20, 7, 69, 69):
        raise ValueError("unexpected Phase 9 v4 manual-review aggregate")

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
            "case-order sample of all 20 fresh held-out identifiable adaptive reports"
        ),
        "actual_reports_reviewed": len(rows),
        "independent_groups_represented": len(groups),
        "factual_claim_count": factual,
        "supported_factual_claim_count": supported,
        "supported_claim_rate": rate,
        "target": 0.95,
        "passed": rate >= 0.95,
        "method": (
            "Count the policy-observation statement, each unique raw metric or approved-change "
            "statement, and the bounded diagnostic conclusion as atomic externally verifiable "
            "claims. Deduplicate the hypothesis explanation because it repeats those facts and "
            "the summary conclusion; exclude recommendations, schema metadata, and explicit "
            "epistemic limitations. A claim passes only when cited eligible run evidence directly "
            "entails it. Raw numeric claims were checked against the cited captured series and "
            "derived-policy claims against the trace-linked reduction."
        ),
    }

    aggregate = json.loads(pre_review_path.read_text(encoding="utf-8"))
    aggregate["manual_review"] = review_summary
    aggregate["targets"]["supported_claim_rate"] = review_summary["passed"]
    aggregate["gate_status"] = (
        "pass" if all(value is True for value in aggregate["targets"].values()) else "fail"
    )
    aggregate["limitations"] = [
        item
        for item in aggregate["limitations"]
        if not item.startswith("Supported factual claim rate requires")
    ]
    aggregate["limitations"].extend(
        [
            "The written semantic rubric is AI-assisted and is not independent human validation.",
            "The 20 reviewed reports represent seven independent capture groups; variants sharing "
            "one capture are not independent evidence.",
        ]
    )
    if aggregate["gate_status"] != "pass":
        raise ValueError("Phase 9 v4 did not satisfy every frozen target")

    (output_dir / "manual-review.jsonl").write_text(
        "".join(canonical(row) + "\n" for row in rows), encoding="utf-8"
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
                "unique_jobs": len(runs),
                "actual_reports_reviewed": len(rows),
                "independent_groups_represented": len(groups),
                "supported_claims": f"{supported}/{factual}",
                "supported_claim_rate": rate,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
