from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from incidentgraph.investigator import (
    ModelResult,
    ModelUsage,
    ToolResult,
    validate_report_citations,
)
from incidentgraph.phase9_repair import (
    POLICY_VERSION,
    ROOT,
    CompactSelection,
    Selection,
    build_observation_workflow,
    build_policy_evidence,
    derive_repair_signal_summary,
    development_records,
    evidence_packet,
    probe,
    prompt_packet,
    reconstructed_high_traffic_record,
    render_report,
    resolve_policy_decision,
    validate_selection,
)
from incidentgraph.phase9_v2_evaluation import ObservationPlan


@pytest.fixture
def dev() -> dict[str, Any]:
    return {r["case_id"].rsplit("-", 1)[1]: r for r in development_records()}


def packet(record: dict[str, Any]) -> dict[str, Any]:
    return evidence_packet([ToolResult.model_validate(t) for t in record["tool_trace"]])


@pytest.mark.parametrize(
    "case,signal",
    [
        ("001", "downstream_latency"),
        ("004", "database_pool_exhaustion"),
        ("007", "dependency_errors"),
        ("010", "cache_degradation"),
        ("013", "deployment_regression"),
        ("016", "cpu_contention"),
        ("019", "dependency_errors"),
    ],
)
def test_known_development_faults_keep_their_numeric_provenance(
    dev: dict[str, Any],
    case: str,
    signal: str,
) -> None:
    p = packet(dev[case])
    assert p["signal_summary"]["active_signals"] == [signal]
    assert not p["signal_summary"]["telemetry_gaps"]
    refs = p["candidate_fact_refs"][signal]
    assert refs
    raw = Selection(
        outcome="probable_cause",
        mechanism=signal,
        component="svc-checkout" if case in {"004", "013"} else "svc-payments",
        supporting_refs=refs,
        explanation="Synthetic test: selected measured lab signal.",
    )
    decision = validate_selection(raw, p)
    assert set(map(str, decision.supporting_evidence_ids)).issubset(dev[case]["evidence_ids"])
    assert len(prompt_packet(p)) < 4000
    assert "evidence_id" not in prompt_packet(p)


@pytest.mark.parametrize("case", ["026", "029"])
def test_missing_or_competing_evidence_cannot_become_a_healthy_report(
    dev: dict[str, Any],
    case: str,
) -> None:
    p = packet(dev[case])
    assert (
        p["signal_summary"]["telemetry_gaps"]
        or p["signal_summary"]["unavailable_measurements"]
        or p["signal_summary"]["ambiguous"]
    )
    with pytest.raises(ValueError, match="inconclusive|contradicts"):
        validate_selection(
            Selection(
                outcome="no_incident_detected",
                component="none",
                mechanism="healthy",
                supporting_refs=["F1"],
                explanation="No incident found.",
            ),
            p,
        )


def test_healthy_development_case_retains_citable_measurements(dev: dict[str, Any]) -> None:
    r = dev["021"]
    p = packet(r)
    assert p["signal_summary"]["bounded_healthy_candidate"]
    decision = validate_selection(
        Selection(
            outcome="no_incident_detected",
            component="none",
            mechanism="healthy",
            supporting_refs=["F1", "F2"],
            explanation="No measured lab threshold was crossed.",
        ),
        p,
    )
    cases = {
        c["case_id"]: c
        for c in map(
            json.loads, (ROOT / "data/evaluation/incident-cases-v3.jsonl").read_text().splitlines()
        )
    }
    evidence = [e for t in r["tool_trace"] for e in ToolResult.model_validate(t).evidence]
    report = render_report(cases[r["case_id"]], decision, p, evidence)
    assert report.observed_symptoms
    assert validate_report_citations(report, evidence) == []


def test_early_adaptive_stop_exposes_missing_change_observation(dev: dict[str, Any]) -> None:
    r = dev["013"]
    partial = [
        ToolResult.model_validate(t) for t in r["tool_trace"] if t["tool"] != "get_recent_changes"
    ]
    p = evidence_packet(partial)
    assert "approved_change_observation" in p["signal_summary"]["telemetry_gaps"]
    assert not p["signal_summary"]["bounded_healthy_candidate"]


@pytest.mark.parametrize("refs", [["F999"], ["F1", "F1"], []])
def test_invalid_or_empty_citations_are_rejected(dev: dict[str, Any], refs: list[str]) -> None:
    with pytest.raises(ValueError):
        validate_selection(
            Selection(
                outcome="probable_cause",
                component="svc-payments",
                mechanism="cpu_contention",
                supporting_refs=refs,
                explanation="CPU fault.",
            ),
            packet(dev["016"]),
        )


def test_fault_is_not_silently_normalized_to_healthy(dev: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="requires that probable cause"):
        validate_selection(
            Selection(
                outcome="no_incident_detected",
                component="none",
                mechanism="healthy",
                supporting_refs=["F1"],
                explanation="The model ignored abnormal telemetry.",
            ),
            packet(dev["001"]),
        )


async def test_probe_offline_is_a_zero_model_policy_replay(tmp_path: Path) -> None:
    result = await probe(tmp_path, offline=True)
    assert result["model_calls"] == 0
    assert result["cases"] == 11
    assert result["correct"] == 11
    assert result["deterministic_support_checks_passed"] == 11
    records = json.loads((tmp_path / "records.json").read_text())
    assert all("-dev-" in r["case_id"] for r in records)
    assert all(r["report"]["usage_and_timing"]["model_calls"] == 0 for r in records)


async def test_omitted_high_traffic_control_is_reconstructed_deterministically() -> None:
    first = await reconstructed_high_traffic_record()
    second = await reconstructed_high_traffic_record()
    assert first == second
    assert first["case_id"] == "incident-v3-dev-024"
    p = evidence_packet([ToolResult.model_validate(item) for item in first["tool_trace"]])
    assert p["signal_summary"]["bounded_healthy_candidate"] is True
    assert p["signal_summary"]["active_signals"] == []
    assert not p["signal_summary"]["telemetry_gaps"]
    assert not p["signal_summary"]["unavailable_measurements"]


async def test_adaptive_workflow_collects_changes_even_when_model_finishes_early(
    dev: dict[str, Any],
) -> None:
    r = dev["013"]
    cases = {
        c["case_id"]: c
        for c in map(
            json.loads, (ROOT / "data/evaluation/incident-cases-v3.jsonl").read_text().splitlines()
        )
    }

    class SavedToolbox:
        async def execute(self, request: Any, context: Any) -> ToolResult:
            for t in r["tool_trace"]:
                if t["tool"] != request.tool.value:
                    continue
                if t["tool"] == "get_metrics" and (
                    t["data"].get("service_id") != request.arguments["service_id"]
                    or t["data"].get("template") != request.arguments["template"]
                ):
                    continue
                return ToolResult.model_validate(t)
            raise AssertionError("unexpected tool request")

    async def early_finish(context: str) -> ModelResult:
        return ModelResult(
            ObservationPlan(
                action="finish",
                bundle=None,
                decision_summary="Model prematurely considers evidence sufficient.",
            ),
            ModelUsage(),
        )

    graph = build_observation_workflow(SavedToolbox(), early_finish)
    state = await graph.ainvoke({"case": cases[r["case_id"]], "investigation_id": str(uuid4())})
    assert len(state["outcomes"]) == 14
    assert state["plan_calls"] == 2
    assert len(state["corrections"]) == 2
    assert evidence_packet(state["outcomes"])["signal_summary"]["active_signals"] == [
        "deployment_regression"
    ]


async def test_policy_probe_has_no_retry_or_model_failure_surface(tmp_path: Path) -> None:
    result = await probe(tmp_path)
    assert result["model_calls"] == 0
    assert result["validation_failures"] == 0
    assert result["first_pass_label_match"] == result["eventual_label_match"] == 11
    records = json.loads((tmp_path / "records.json").read_text())
    assert all("attempts" not in record for record in records)
    assert all(record["decision_source"] == "trusted_bounded_policy" for record in records)


def test_returned_probe_is_preserved_as_failure_evidence() -> None:
    fixture = json.loads((ROOT / "tests/fixtures/phase9-repair-responses.json").read_text())
    assert fixture["failure_counts"] == {
        "no_response": 1,
        "schema_coherence": 10,
        "citation_limit": 9,
    }
    responses = [
        a["response"]["message"]["content"] for a in fixture["responses"] if "response" in a
    ]
    # Never reinterpret an old inconclusive outcome as a successful probable cause.
    assert len(responses) == 19
    assert all(json.loads(text)["outcome"] == "inconclusive" for text in responses)


def test_returned_repair2_archive_is_preserved_without_rescoring() -> None:
    root = ROOT / "artifacts/evaluation/phase9-repair2-probe"
    summary = json.loads((root / "summary.json").read_text())
    records = json.loads((root / "records.json").read_text())
    assert summary["probe_version"] == "repair-2"
    assert summary["valid_reports"] == 10
    assert summary["correct"] == 7
    assert summary["model_calls"] == 11
    assert len(records) == 10
    assert {record["case_id"] for record in records if not record["correct"]} == {
        "incident-v3-dev-007",
        "incident-v3-dev-019",
        "incident-v3-dev-021",
    }


@pytest.mark.parametrize(
    "decision",
    [
        "downstream_latency",
        "database_pool_exhaustion",
        "dependency_errors",
        "cache_degradation",
        "deployment_regression",
        "cpu_contention",
        "healthy",
        "healthy_high_traffic",
        "insufficient_observation",
    ],
)
def test_transport_cannot_express_the_returned_cross_field_contradictions(decision: str) -> None:
    from incidentgraph.phase9_v2_evaluation import DiagnosisDecision

    raw = CompactSelection(
        decision=decision, evidence_refs=["F1"], rationale="A short bounded rationale."
    )
    expanded = raw.expanded()
    DiagnosisDecision.model_validate(
        {
            **expanded.model_dump(exclude={"supporting_refs"}),
            "supporting_evidence_ids": [],
        }
    )
    if decision == "insufficient_observation":
        assert expanded.outcome == "inconclusive"
        assert expanded.component == "none" and expanded.limitation


def test_transport_citation_limit_matches_report_source_limit() -> None:
    with pytest.raises(ValueError):
        CompactSelection(
            decision="healthy",
            evidence_refs=["F1", "F2", "F3", "F4"],
            rationale="Too many sources.",
        )


def test_cpu_candidate_references_only_abnormal_payments_cpu(dev: dict[str, Any]) -> None:
    p = packet(dev["016"])
    refs = p["candidate_fact_refs"]["cpu_contention"]
    assert len(refs) == 1
    fact = next(f for f in p["facts"] if f["ref"] == refs[0])
    assert fact["labels"]["job"] == "payments"
    assert fact["service"] == "svc-payments"
    assert all(
        f["service"] == "svc-" + f["labels"]["job"]
        for f in p["facts"]
        if f["source"] == "process_cpu"
    )


def test_checkout_deployment_does_not_require_zero_payments_errors_as_support(
    dev: dict[str, Any],
) -> None:
    p = packet(dev["013"])
    refs = p["candidate_fact_refs"]["deployment_regression"]
    cited = [f for f in p["facts"] if f["ref"] in refs]
    assert len(cited) == 2
    assert all(f.get("maximum", f.get("count")) >= 1 for f in cited)


async def test_policy_replay_reaches_reports_and_scoring(tmp_path: Path) -> None:
    result = await probe(tmp_path)
    # Development policy replay, not evidence of free-form model accuracy or held-out quality.
    assert result["valid_reports"] == 11
    assert result["validation_failures"] == 0
    assert result["model_calls"] == 0
    assert result["correct"] == 11
    assert result["per_case_type"] == {
        "identifiable": {"correct": 7, "total": 7},
        "insufficient": {"correct": 2, "total": 2},
        "healthy": {"correct": 2, "total": 2},
    }
    assert any("healthy-high-traffic" in item for item in result["limitations"])


def test_policy_resolution_uses_exact_service_scoped_facts(dev: dict[str, Any]) -> None:
    record = dev["016"]
    p = packet(record)
    case = next(
        item
        for item in map(
            json.loads, (ROOT / "data/evaluation/incident-cases-v3.jsonl").read_text().splitlines()
        )
        if item["case_id"] == record["case_id"]
    )
    trace_hash = "a" * 64
    derived = build_policy_evidence(
        p, case, source_job_id=record["job_id"], source_trace_sha256=trace_hash
    )
    resolution = resolve_policy_decision(p, derived)
    assert resolution.decision.mechanism == "cpu_contention"
    assert resolution.selected_fact_refs == ["F12"]
    evidence = [
        item for trace in record["tool_trace"] for item in ToolResult.model_validate(trace).evidence
    ]
    report = render_report(
        case,
        resolution.decision,
        p,
        [*evidence, derived],
        selected_fact_refs=resolution.selected_fact_refs,
        source_job_id=record["job_id"],
        source_trace_sha256=trace_hash,
    )
    metric_observations = [
        item.description for item in report.observed_symptoms if "process_cpu" in item.description
    ]
    assert len(metric_observations) == 1
    assert "payments" in metric_observations[0]
    assert "gateway" not in metric_observations[0]
    assert report.target_service == f"svc-{case['target_service']}"
    assert POLICY_VERSION in report.trace_reference
    assert trace_hash in report.trace_reference
    assert report.usage_and_timing.model_calls == 0
    assert report.usage_and_timing.tool_calls == 0


def test_policy_evidence_covers_every_fact_source_and_trace(dev: dict[str, Any]) -> None:
    record = dev["021"]
    p = packet(record)
    case = next(
        item
        for item in map(
            json.loads, (ROOT / "data/evaluation/incident-cases-v3.jsonl").read_text().splitlines()
        )
        if item["case_id"] == record["case_id"]
    )
    trace_hash = "b" * 64
    derived = build_policy_evidence(
        p, case, source_job_id=record["job_id"], source_trace_sha256=trace_hash
    )
    content = json.loads(derived.content or "{}")
    assert content["source_trace_sha256"] == trace_hash
    assert set(content["source_evidence_ids"]) == {fact["evidence_id"] for fact in p["facts"]}
    assert content["bounded_healthy_candidate"] is True
    resolution = resolve_policy_decision(p, derived)
    assert resolution.decision.outcome == "no_incident_detected"
    assert resolution.decision.supporting_evidence_ids == [derived.evidence_id]


def test_unrelated_change_cannot_create_checkout_deployment_signal(dev: dict[str, Any]) -> None:
    p = packet(dev["013"])
    facts = [dict(fact) for fact in p["facts"]]
    for fact in facts:
        if fact["source"] == "approved_changes":
            fact["service"] = "payments"
    summary = derive_repair_signal_summary(
        facts,
        telemetry_gaps=[],
        unavailable_measurements=[],
        changes_observed=True,
    )
    assert "deployment_regression" not in summary["active_signals"]


def test_pool_signal_survives_missing_success_latency_samples(dev: dict[str, Any]) -> None:
    record = dev["004"]
    p = packet(record)
    assert p["signal_summary"]["unavailable_measurements"]
    case = next(
        item
        for item in map(
            json.loads, (ROOT / "data/evaluation/incident-cases-v3.jsonl").read_text().splitlines()
        )
        if item["case_id"] == record["case_id"]
    )
    derived = build_policy_evidence(
        p, case, source_job_id=record["job_id"], source_trace_sha256="c" * 64
    )
    resolution = resolve_policy_decision(p, derived)
    assert resolution.decision.mechanism == "database_pool_exhaustion"
    assert resolution.decision.component == "svc-checkout"
