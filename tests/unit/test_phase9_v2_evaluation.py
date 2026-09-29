from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from incidentgraph.config import Settings
from incidentgraph.investigator import (
    ModelResult,
    ModelUsage,
    ToolName,
    ToolRequest,
    ToolResult,
    ToolRuntimeContext,
)
from incidentgraph.models import EvidenceItem, ReportOutcome
from incidentgraph.phase9_evaluation import AUTHORIZED_SERVICES
from incidentgraph.phase9_v2_evaluation import (
    AdaptiveState,
    DiagnosisDecision,
    ObservationPlan,
    _build_report,
    _bundle_requests,
    _initial_requests,
    build_adaptive_workflow,
    compact_context,
    compact_outcome,
)


def _case() -> dict[str, object]:
    return {
        "case_id": "incident-dev-001",
        "question": "Investigate the bounded checkout symptom.",
        "target_service": "gateway",
        "snapshot_id": "cap-20260922214548-14c491f743",
        "window_start": "2026-09-22T21:45:48+00:00",
        "window_end": "2026-09-22T21:46:00+00:00",
        "observation_cutoff": "2026-09-22T21:46:00+00:00",
    }


def _settings() -> Settings:
    return Settings(  # type: ignore[call-arg]
        app_database_dsn="postgresql://unit:unit@127.0.0.1:5432/app",
        lab_database_dsn="postgresql://unit:unit@127.0.0.1:5433/lab",
        neo4j_uri="bolt://127.0.0.1:7687",
        neo4j_password="unit-test-password",
    )


def _evidence() -> EvidenceItem:
    now = datetime(2026, 9, 22, 21, 46, tzinfo=UTC)
    return EvidenceItem(
        evidence_id=uuid4(),
        kind="metric",
        source_id="metrics.json#cpu_time",
        source_version="1",
        service_ids=["svc-payments"],
        environment="lab",
        observed_at=now,
        collected_at=now,
        content_hash="a" * 64,
        freshness_status="fresh",
        provenance_reference="capture://example/metrics",
        window_start=now,
        window_end=now,
        valid_from=now,
        snapshot_id="cap-20260922214548-14c491f743",
    )


def test_v2_requests_are_code_built_and_share_the_same_fourteen_call_cap() -> None:
    case = _case()
    initial = _initial_requests(case, "svc-gateway")
    resource = _bundle_requests(case, "resource_signals")
    context = _bundle_requests(case, "context_signals")

    assert 1 + len(initial) + len(resource) + len(context) == 14
    assert len(initial) == 8
    assert all(
        request.arguments.get("service_id") in AUTHORIZED_SERVICES
        for request in initial
        if "service_id" in request.arguments
    )
    assert all(
        request.arguments.get("window_start") == case["window_start"]
        for request in [*initial, *resource, *context]
        if "window_start" in request.arguments
    )


def test_compaction_excludes_success_series_from_error_rate() -> None:
    result = ToolResult(
        tool=ToolName.GET_METRICS,
        status="ok",
        summary="returned two bounded metric series",
        data={
            "template": "error_rate",
            "series_summaries": [
                {
                    "template_source": "dependency_outcomes",
                    "metric": {
                        "service": "checkout",
                        "dependency": "payments",
                        "outcome": "success",
                    },
                    "maximum": 6.0,
                    "unit": "requests/second",
                },
                {
                    "template_source": "dependency_outcomes",
                    "metric": {
                        "service": "checkout",
                        "dependency": "payments",
                        "outcome": "error",
                    },
                    "maximum": 3.0,
                    "unit": "requests/second",
                },
            ],
        },
    )

    compact = compact_outcome(result)

    assert len(compact["data"]["series_summaries"]) == 1
    assert compact["data"]["series_summaries"][0]["metric"]["outcome"] == "error"
    context = compact_context(_case(), "svc-gateway", [result])
    assert len(context) < 12_000


def test_invalid_citation_downgrades_cause_to_honest_inconclusive() -> None:
    evidence = _evidence()
    decision = DiagnosisDecision(
        outcome="probable_cause",
        component="svc-payments",
        mechanism="cpu_contention",
        supporting_evidence_ids=[uuid4()],
        explanation="Payments CPU is elevated.",
    )
    case = _case()

    report = _build_report(
        case=case,
        investigation_id=uuid4(),
        service_id="svc-gateway",
        decision=decision,
        evidence=[evidence],
        model_calls=1,
        tool_calls=14,
        input_tokens=500,
        output_tokens=100,
        model_latency_ms=10,
        tool_latency_ms=5,
        active_duration_ms=20,
        workflow="adaptive",
    )

    assert report.outcome == ReportOutcome.INCONCLUSIVE
    assert report.ranked_hypotheses == []
    assert report.limitations


def test_v2_structured_decisions_reject_incoherent_outputs() -> None:
    with pytest.raises(ValidationError):
        DiagnosisDecision(
            outcome="probable_cause",
            component="none",
            mechanism="healthy",
            explanation="This is not coherent.",
        )
    with pytest.raises(ValidationError):
        ObservationPlan(action="observe", bundle=None, decision_summary="Need evidence.")


class _FakeModel:
    async def plan(self, context: str) -> ModelResult:
        return ModelResult(
            ObservationPlan(
                action="observe",
                bundle="resource_signals",
                decision_summary="Inspect resource discriminators.",
            ),
            ModelUsage(),
        )

    async def diagnose(self, context: str) -> ModelResult:
        return ModelResult(
            DiagnosisDecision(
                outcome="no_incident_detected",
                component="none",
                mechanism="healthy",
                explanation="No bounded fault signal is present.",
            ),
            ModelUsage(),
        )


def test_fake_model_conforms_to_v2_protocol_shape() -> None:
    model = _FakeModel()
    assert model is not None


class _FakeToolbox:
    async def execute(self, request: ToolRequest, context: ToolRuntimeContext) -> ToolResult:
        if request.tool == ToolName.RESOLVE_SERVICE:
            return ToolResult(
                tool=request.tool,
                status="ok",
                summary="resolved gateway to svc-gateway",
                data={"service_id": "svc-gateway", "name": "gateway"},
            )
        evidence = _evidence().model_copy(
            update={
                "evidence_id": uuid4(),
                "source_id": f"fake#{request.tool.value}",
                "kind": "topology" if request.tool == ToolName.GET_DEPENDENCIES else "metric",
            }
        )
        return ToolResult(
            tool=request.tool,
            status="ok",
            summary=f"bounded {request.tool.value} observation",
            evidence=(evidence,),
            data={},
        )


@pytest.mark.asyncio
async def test_adaptive_langgraph_executes_bounded_bundles_without_raw_model_arguments() -> None:
    initial: AdaptiveState = {
        "case": _case(),
        "investigation_id": str(uuid4()),
        "outcomes": [],
        "evidence": [],
        "remaining_bundles": [],
        "bundle_rounds": 0,
        "next_action": "observe",
        "selected_bundle": None,
        "decision_summaries": [],
        "errors": [],
        "model_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "model_latency_ms": 0,
        "tool_latency_ms": 0,
        "report": None,
    }
    workflow = build_adaptive_workflow(  # type: ignore[arg-type]
        _settings(), _FakeModel(), _FakeToolbox()
    )

    state = await workflow.ainvoke(initial, config={"recursion_limit": 16})

    assert state["report"].outcome == ReportOutcome.NO_INCIDENT_DETECTED
    assert state["model_calls"] == 3
    assert len(state["outcomes"]) == 14
    assert state["errors"] == []
