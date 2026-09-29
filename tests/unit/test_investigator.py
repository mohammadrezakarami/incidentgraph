from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from incidentgraph.config import Settings
from incidentgraph.investigation_tools import CaptureToolbox
from incidentgraph.investigator import (
    BudgetExceeded,
    HypothesisRevision,
    InvestigatorState,
    LogsInput,
    MetricsInput,
    ModelResult,
    ModelUsage,
    PlanDecision,
    PolicyViolation,
    ReportDraft,
    RetrieveInput,
    ToolName,
    ToolRequest,
    ToolResult,
    ToolRuntimeContext,
    _reserve_model_call,
    build_workflow,
    initial_state,
    investigator_status,
    request_fingerprint,
    validate_report_citations,
    validate_tool_request,
)
from incidentgraph.models import (
    EvidenceItem,
    EvidenceStrength,
    ImpactStatement,
    IncidentWindow,
    InvestigationMode,
    InvestigationReport,
    RankedHypothesis,
    RecommendedNextStep,
    ReportOutcome,
    UsageAndTiming,
)


def settings(**updates: object) -> Settings:
    base = Settings(
        environment="test",
        app_database_dsn="postgresql://app:test@localhost/app",
        lab_database_dsn="postgresql://lab:test@localhost/lab",
        neo4j_uri="bolt://localhost:7687",
        neo4j_password="test-only-password",
        auth_tokens_json="{}",
    )
    return base.model_copy(update=updates)


def evidence(source: str = "metric-request-latency") -> EvidenceItem:
    now = datetime(2026, 9, 23, 12, tzinfo=UTC)
    return EvidenceItem(
        evidence_id=uuid5(NAMESPACE_URL, source),
        kind="metric",
        source_id=source,
        source_version="1",
        service_ids=["svc-gateway"],
        environment="lab",
        observed_at=now,
        collected_at=now,
        content_hash="a" * 64,
        freshness_status="fresh",
        provenance_reference=f"capture://test/{source}",
        content="bounded metric observation",
    )


class FakeTools:
    def __init__(self, selected_tool: ToolName, *, fail_observation: bool = False) -> None:
        self.selected_tool = selected_tool
        self.fail_observation = fail_observation
        self.seen: list[ToolName] = []
        self.item = evidence(selected_tool.value)

    async def execute(self, request: ToolRequest, context: ToolRuntimeContext) -> ToolResult:
        del context
        self.seen.append(request.tool)
        if request.tool == ToolName.RESOLVE_SERVICE:
            return ToolResult(
                tool=request.tool,
                status="ok",
                summary="resolved gateway",
                data={"service_id": "svc-gateway"},
            )
        assert request.tool == self.selected_tool
        if self.fail_observation:
            return ToolResult(
                tool=request.tool,
                status="error",
                summary="telemetry is absent",
                error_code="INSUFFICIENT_DATA",
            )
        return ToolResult(
            tool=request.tool,
            status="ok",
            summary="bounded observation returned",
            evidence=(self.item,),
            data={"signal": "observed"},
        )


class ScriptedModel:
    def __init__(
        self,
        selected_tool: ToolName,
        item: EvidenceItem,
        *,
        inconclusive: bool = False,
    ) -> None:
        self.selected_tool = selected_tool
        self.item = item
        self.inconclusive = inconclusive

    def _tool_request(self, context: str) -> ToolRequest:
        state = json.loads(context)
        start, end = state["window"]
        diagnostic_round = len(
            [
                item
                for item in state["tool_outcomes"]
                if item["tool"] not in {"resolve_service", "get_service_context"}
            ]
        )
        if self.selected_tool == ToolName.GET_METRICS:
            metric_template = "request_latency" if diagnostic_round == 0 else "cpu_time"
            arguments: dict[str, Any] = MetricsInput(
                service_id="svc-gateway",
                template=metric_template,
                window_start=start,
                window_end=end,
                resolution_seconds=1,
            ).model_dump(mode="json")
        else:
            arguments = {
                "service_ids": ["svc-gateway"],
                "window_start": start,
                "window_end": end,
                "event": ("request.failure" if diagnostic_round == 0 else "dependency.failure"),
                "limit": 20,
            }
        return ToolRequest(
            tool=self.selected_tool,
            arguments=arguments,
            reason="Inspect the strongest unresolved signal.",
        )

    async def plan(self, context: str) -> ModelResult:
        return ModelResult(
            PlanDecision(
                action="observe",
                objective="Inspect the reported symptom.",
                decision_summary=f"Selected {self.selected_tool.value} for the first observation.",
                tool_request=self._tool_request(context),
            ),
            ModelUsage(input_tokens=20, output_tokens=10, latency_ms=1),
        )

    async def update_hypotheses(self, context: str) -> ModelResult:
        del context
        hypotheses = []
        if not self.inconclusive:
            hypotheses = [
                RankedHypothesis(
                    rank=1,
                    mechanism="elevated request latency",
                    suspected_component="svc-gateway",
                    evidence_strength=EvidenceStrength.MEDIUM,
                    supporting_evidence_ids=[self.item.evidence_id],
                    explanation_summary="The bounded observation supports the mechanism.",
                    additional_evidence_needed=[],
                )
            ]
        return ModelResult(
            HypothesisRevision(
                hypotheses=hypotheses,
                missing_information=["payments metrics"] if self.inconclusive else [],
                contradictions=[],
                sufficient=True,
                decision_summary=(
                    "Telemetry is missing, so the result must abstain."
                    if self.inconclusive
                    else "The observation is sufficient for a bounded report."
                ),
            ),
            ModelUsage(input_tokens=20, output_tokens=10, latency_ms=1),
        )

    async def draft_report(self, context: str) -> ModelResult:
        del context
        if self.inconclusive:
            draft = ReportDraft(
                outcome="inconclusive",
                summary="Available telemetry is insufficient for a supported cause.",
                limitations=["The requested telemetry signal is missing."],
            )
        else:
            draft = ReportDraft(
                outcome="probable_cause",
                summary="The observed symptom is supported by bounded evidence.",
                observed_symptoms=[
                    ImpactStatement(
                        description="Request latency increased in the incident window.",
                        evidence_ids=[self.item.evidence_id],
                    )
                ],
                ranked_hypotheses=[
                    RankedHypothesis(
                        rank=1,
                        mechanism="elevated request latency",
                        suspected_component="svc-gateway",
                        evidence_strength="medium",
                        supporting_evidence_ids=[self.item.evidence_id],
                        explanation_summary="The metric directly supports the symptom.",
                    )
                ],
                limitations=["Laboratory evidence only."],
            )
        return ModelResult(
            draft,
            ModelUsage(input_tokens=20, output_tokens=10, latency_ms=1),
        )


def state() -> InvestigatorState:
    end = datetime(2026, 9, 23, 12, tzinfo=UTC)
    return initial_state(
        investigation_id=uuid4(),
        request_id=uuid4(),
        principal_id="viewer-1",
        authorized_service_ids=("svc-gateway", "svc-checkout", "svc-payments"),
        question="Why did gateway requests slow down in this window?",
        target_service="gateway",
        window_start=end - timedelta(minutes=5),
        window_end=end,
        observation_cutoff=end,
        mode=InvestigationMode.REPLAY,
        snapshot_id="cap-test-00000000",
        corpus_version="test-corpus-v1",
    )


def test_follow_up_model_budget_is_incremental_over_cumulative_usage() -> None:
    current = state()
    current["counters"] = {
        "model_calls": 5,
        "tool_calls": 4,
        "rounds": 2,
        "input_tokens": 100,
        "output_tokens": 50,
        "estimated_cost_usd": 0,
        "model_latency_ms": 10,
        "tool_latency_ms": 10,
        "repair_attempts": 0,
        "tool_validation_retries": 0,
    }
    current["revision_model_calls_start"] = 5
    current["revision_max_model_calls"] = 2

    first = _reserve_model_call(current, settings(), "bounded context")
    current["counters"] = first.model_dump(mode="json")
    second = _reserve_model_call(current, settings(), "bounded context")
    current["counters"] = second.model_dump(mode="json")

    with pytest.raises(BudgetExceeded, match="follow-up model-call"):
        _reserve_model_call(current, settings(), "bounded context")


@pytest.mark.asyncio
@pytest.mark.parametrize("selected_tool", [ToolName.GET_METRICS, ToolName.SEARCH_LOGS])
async def test_adaptive_workflow_can_choose_different_first_observations(
    selected_tool: ToolName,
) -> None:
    tools = FakeTools(selected_tool)
    model = ScriptedModel(selected_tool, tools.item)
    workflow = build_workflow(settings(), model, tools)

    result = await workflow.ainvoke(state())

    assert result["status"] == "completed"
    assert result["report_valid"] is True
    assert tools.seen == [ToolName.RESOLVE_SERVICE, selected_tool, selected_tool]
    assert selected_tool.value in result["decision_summaries"][0]
    assert result["counters"]["model_calls"] == 5
    assert result["counters"]["tool_calls"] == 3
    assert result["evidence"][0]["content"] is None
    assert result["hypothesis_version"] == 2
    assert result["report_version"] == 1
    assert result["report_reference"].startswith("postgres://incidentgraph_app/reports/")


@pytest.mark.asyncio
async def test_human_review_interrupt_resumes_and_preserves_state_across_revision() -> None:
    tools = FakeTools(ToolName.GET_METRICS)
    model = ScriptedModel(ToolName.GET_METRICS, tools.item)
    initial = state()
    workflow = build_workflow(
        settings(human_review_required=True),
        model,
        tools,
        checkpointer=InMemorySaver(),
    )
    config = {"configurable": {"thread_id": initial["thread_id"]}}

    waiting = await workflow.ainvoke(initial, config=config)
    review = waiting["__interrupt__"][0].value
    assert review["report_version"] == 1
    assert review["allowed_decisions"] == ["accept", "reject", "request_revision"]
    evidence_ids = [item["evidence_id"] for item in waiting["evidence"]]
    counters_before = waiting["counters"]

    revised = await workflow.ainvoke(
        Command(
            resume={
                "decision": "request_revision",
                "decision_reference": "postgres://review/decision-1",
            }
        ),
        config=config,
    )
    second_review = revised["__interrupt__"][0].value
    assert second_review["report_version"] == 2
    assert [item["evidence_id"] for item in revised["evidence"]] == evidence_ids
    assert revised["counters"]["tool_calls"] == counters_before["tool_calls"]
    assert revised["counters"]["model_calls"] > counters_before["model_calls"]

    completed = await workflow.ainvoke(
        Command(
            resume={
                "decision": "accept",
                "decision_reference": "postgres://review/decision-2",
            }
        ),
        config=config,
    )
    assert completed["status"] == "completed"
    assert completed["report_version"] == 2


class InvalidThenCorrectModel(ScriptedModel):
    def __init__(self, selected_tool: ToolName, item: EvidenceItem) -> None:
        super().__init__(selected_tool, item)
        self.plan_calls = 0

    async def plan(self, context: str) -> ModelResult:
        self.plan_calls += 1
        if self.plan_calls == 1:
            state = json.loads(context)
            return ModelResult(
                PlanDecision(
                    action="observe",
                    objective="Inspect the reported symptom.",
                    decision_summary="The first local-model request is deliberately malformed.",
                    tool_request=ToolRequest(
                        tool=ToolName.GET_METRICS,
                        arguments={
                            "service_id": "svc-gateway",
                            "observation_time": state["observation_cutoff"],
                        },
                        reason="Exercise bounded validation repair.",
                    ),
                ),
                ModelUsage(input_tokens=20, output_tokens=10, latency_ms=1),
            )
        return await super().plan(context)


@pytest.mark.asyncio
async def test_invalid_local_model_tool_arguments_get_one_bounded_retry() -> None:
    tools = FakeTools(ToolName.GET_METRICS)
    model = InvalidThenCorrectModel(ToolName.GET_METRICS, tools.item)
    workflow = build_workflow(settings(), model, tools)

    result = await workflow.ainvoke(state())

    assert result["status"] == "completed"
    assert result["counters"]["tool_validation_retries"] == 1
    assert any("invalid get_metrics arguments" in item for item in result["error_summaries"])
    assert tools.seen == [ToolName.RESOLVE_SERVICE, ToolName.GET_METRICS, ToolName.GET_METRICS]


@pytest.mark.asyncio
async def test_missing_telemetry_produces_an_inconclusive_report() -> None:
    tools = FakeTools(ToolName.GET_METRICS, fail_observation=True)
    model = ScriptedModel(ToolName.GET_METRICS, tools.item, inconclusive=True)
    workflow = build_workflow(settings(), model, tools)

    result = await workflow.ainvoke(state())

    report = InvestigationReport.model_validate(result["report"])
    assert result["status"] == "inconclusive"
    assert report.outcome == ReportOutcome.INCONCLUSIVE
    assert report.limitations
    assert report.ranked_hypotheses == []


def test_policy_rejects_unauthorized_and_duplicate_tool_calls() -> None:
    now = datetime(2026, 9, 23, 12, tzinfo=UTC)
    runtime = ToolRuntimeContext(
        investigation_id=uuid4(),
        principal_id="viewer-1",
        authorized_service_ids=("svc-gateway",),
        environment="lab",
        window_start=now - timedelta(minutes=10),
        window_end=now,
        observation_cutoff=now,
        snapshot_id="cap-test-00000000",
    )
    unauthorized = ToolRequest(
        tool=ToolName.RETRIEVE_RUNBOOKS,
        arguments=RetrieveInput(
            query="Find a cache runbook",
            service_ids=("svc-payments",),
            cutoff=now,
        ).model_dump(mode="json"),
        reason="Inspect a runbook.",
    )
    with pytest.raises(PolicyViolation, match="unauthorized"):
        validate_tool_request(unauthorized, runtime, [])

    allowed = unauthorized.model_copy(
        update={
            "arguments": RetrieveInput(
                query="Find a gateway runbook",
                service_ids=("svc-gateway",),
                cutoff=now,
            ).model_dump(mode="json")
        }
    )
    fingerprint = request_fingerprint(allowed)
    with pytest.raises(PolicyViolation, match="duplicate"):
        validate_tool_request(allowed, runtime, [fingerprint])


def test_policy_drops_unsupported_null_keys_without_broadening_request() -> None:
    now = datetime(2026, 9, 23, 12, tzinfo=UTC)
    runtime = ToolRuntimeContext(
        investigation_id=uuid4(),
        principal_id="viewer-1",
        authorized_service_ids=("svc-gateway",),
        environment="lab",
        window_start=now - timedelta(minutes=10),
        window_end=now,
        observation_cutoff=now,
        snapshot_id="cap-test-00000000",
    )
    request = ToolRequest(
        tool=ToolName.SEARCH_LOGS,
        arguments={
            "service_ids": ["svc-gateway"],
            "window_start": (now - timedelta(minutes=10)).isoformat(),
            "window_end": now.isoformat(),
            "event_id": None,
            "limit": 20,
        },
        reason="Inspect bounded logs.",
    )

    validated, _ = validate_tool_request(request, runtime, [])

    assert validated.model_dump()["limit"] == 20


@pytest.mark.asyncio
async def test_replay_dependencies_use_the_immutable_capture(tmp_path: Path) -> None:
    snapshot_id = "cap-test-dependencies"
    capture = tmp_path / snapshot_id
    capture.mkdir()
    (capture / "topology.json").write_text(
        json.dumps(
            {
                "services": ["gateway", "checkout", "payments"],
                "dependencies": [
                    {"caller": "gateway", "callee": "checkout"},
                    {"caller": "checkout", "callee": "payments"},
                ],
            }
        ),
        encoding="utf-8",
    )
    now = datetime(2026, 9, 23, 12, tzinfo=UTC)
    runtime = ToolRuntimeContext(
        investigation_id=uuid4(),
        principal_id="viewer-1",
        authorized_service_ids=("svc-gateway", "svc-checkout", "svc-payments"),
        environment="lab",
        window_start=now - timedelta(minutes=10),
        window_end=now,
        observation_cutoff=now,
        snapshot_id=snapshot_id,
    )
    toolbox = CaptureToolbox(settings(), capture_root=tmp_path)
    request = ToolRequest(
        tool=ToolName.GET_DEPENDENCIES,
        arguments={
            "service_id": "svc-gateway",
            "direction": "outbound",
            "depth": 2,
            "observation_time": now.isoformat(),
        },
        reason="Inspect captured dependencies.",
    )

    result = await toolbox.execute(request, runtime)

    assert result.status == "ok"
    assert result.data["path_count"] == 2
    assert result.data["relationships"] == [
        "svc-checkout->svc-payments",
        "svc-gateway->svc-checkout",
    ]
    assert result.evidence[0].source_id == "topology.json#dependencies"


def test_report_validator_rejects_unknown_or_unsupported_citations() -> None:
    item = evidence()
    unknown = uuid4()
    report = InvestigationReport(
        investigation_id=uuid4(),
        report_version=1,
        mode="replay",
        snapshot_id="cap-test-00000000",
        target_service="svc-gateway",
        environment="lab",
        incident_window=IncidentWindow(
            start=datetime(2026, 9, 23, 11, 55, tzinfo=UTC),
            end=datetime(2026, 9, 23, 12, tzinfo=UTC),
        ),
        observation_cutoff=datetime(2026, 9, 23, 12, tzinfo=UTC),
        outcome="probable_cause",
        summary="A bounded probable cause.",
        ranked_hypotheses=[
            RankedHypothesis(
                rank=1,
                mechanism="dependency latency",
                suspected_component="svc-payments",
                evidence_strength="medium",
                supporting_evidence_ids=[unknown],
                explanation_summary="The evidence would support this if it were eligible.",
            )
        ],
        limitations=["Laboratory evidence only."],
        termination_reason="evidence_sufficient",
        usage_and_timing=UsageAndTiming(
            model_calls=3,
            tool_calls=2,
            input_tokens=100,
            output_tokens=100,
            estimated_cost_usd=0,
            active_duration_ms=10,
            model_latency_ms=5,
            tool_latency_ms=5,
        ),
        trace_reference="trace://test",
    )

    errors = validate_report_citations(report, [item])

    assert errors
    assert str(unknown) in errors[0]


def test_workflow_contains_every_required_phase5_lifecycle_node() -> None:
    tools = FakeTools(ToolName.GET_METRICS)
    workflow = build_workflow(settings(), ScriptedModel(ToolName.GET_METRICS, tools.item), tools)

    nodes = set(workflow.get_graph().nodes)

    assert {
        "validate_request",
        "resolve_context",
        "plan_next_observation",
        "enforce_policy",
        "execute_tools",
        "normalize_evidence",
        "update_hypotheses",
        "check_sufficiency",
        "draft_report",
        "validate_report",
        "human_review",
        "finalize",
    }.issubset(nodes)


def test_disabled_provider_is_reported_as_blocked_without_paid_calls(tmp_path: Path) -> None:
    result = investigator_status(settings(), tmp_path / "missing-gate.json")

    assert result["deterministic_workflow"] == "ready"
    assert result["real_model_gate"] == "blocked"
    assert result["paid_calls_allowed"] is False


def test_verified_zero_cost_gate_is_reported_as_passed(tmp_path: Path) -> None:
    gate = tmp_path / "gate-results.json"
    gate.write_text(
        json.dumps(
            {
                "provider": "local_openai_compatible",
                "paid_calls": False,
                "model": {"name": "local-model", "digest": "a" * 64},
                "heldout_seal_before": {
                    "digest": "b" * 64,
                    "heldout_evaluated": False,
                },
                "heldout_seal_after": {
                    "digest": "b" * 64,
                    "heldout_evaluated": False,
                },
                "runs": [{}, {}],
                "gate": {"status": "pass", "checks": {"zero_cost": True}},
            }
        ),
        encoding="utf-8",
    )

    result = investigator_status(settings(), gate)

    assert result["implementation"] == "complete"
    assert result["real_model_gate"] == "passed"
    assert result["real_model_blockers"] == []
    assert result["verified_gate"]["cases"] == 2


class InvalidPlanModel(ScriptedModel):
    async def plan(self, context: str) -> ModelResult:
        del context
        return ModelResult(
            ReportDraft(
                outcome="inconclusive",
                summary="This is the wrong boundary type.",
                limitations=["Deliberately invalid model fixture."],
            ),
            ModelUsage(input_tokens=10, output_tokens=10),
        )


@pytest.mark.asyncio
async def test_invalid_model_boundary_type_fails_explicitly() -> None:
    tools = FakeTools(ToolName.GET_METRICS)
    workflow = build_workflow(settings(), InvalidPlanModel(ToolName.GET_METRICS, tools.item), tools)

    result = await workflow.ainvoke(state())

    assert result["status"] == "failed"
    assert any("expected PlanDecision" in error for error in result["error_summaries"])


class NeverCalledModel(ScriptedModel):
    def __init__(self, selected_tool: ToolName, item: EvidenceItem) -> None:
        super().__init__(selected_tool, item)
        self.calls = 0

    async def plan(self, context: str) -> ModelResult:
        self.calls += 1
        return await super().plan(context)

    async def draft_report(self, context: str) -> ModelResult:
        self.calls += 1
        return await super().draft_report(context)


@pytest.mark.asyncio
async def test_token_budget_is_checked_before_model_call() -> None:
    tools = FakeTools(ToolName.GET_METRICS)
    model = NeverCalledModel(ToolName.GET_METRICS, tools.item)
    constrained = settings(model_token_budget=1_000, model_max_output_tokens=1_200)
    workflow = build_workflow(constrained, model, tools)

    result = await workflow.ainvoke(state())

    assert result["status"] == "inconclusive"
    assert result["report_valid"] is True
    assert result["termination_reason"] == "deterministic_partial_report"
    assert model.calls == 0
    assert any("token budget" in error for error in result["error_summaries"])


def test_time_window_and_plan_models_reject_unsafe_shapes() -> None:
    now = datetime(2026, 9, 23, 12, tzinfo=UTC)
    with pytest.raises(ValueError, match="later"):
        MetricsInput(
            service_id="svc-gateway",
            template="request_latency",
            window_start=now,
            window_end=now,
        )
    with pytest.raises(ValueError, match="60 minutes"):
        MetricsInput(
            service_id="svc-gateway",
            template="request_latency",
            window_start=now - timedelta(minutes=61),
            window_end=now,
        )
    with pytest.raises(ValueError, match="later"):
        LogsInput(
            service_ids=("svc-gateway",),
            window_start=now,
            window_end=now,
        )
    with pytest.raises(ValueError, match="60 minutes"):
        LogsInput(
            service_ids=("svc-gateway",),
            window_start=now - timedelta(minutes=61),
            window_end=now,
        )
    with pytest.raises(ValueError, match="exactly one"):
        PlanDecision(
            action="finish",
            objective="Finish the investigation.",
            decision_summary="No further observation is needed.",
            tool_request=ToolRequest(
                tool=ToolName.RESOLVE_SERVICE,
                arguments={"name": "gateway", "environment": "lab"},
                reason="This request is deliberately incompatible with finish.",
            ),
        )


def test_policy_rejects_environment_time_and_cutoff_expansion() -> None:
    now = datetime(2026, 9, 23, 12, tzinfo=UTC)
    runtime = ToolRuntimeContext(
        investigation_id=uuid4(),
        principal_id="viewer-1",
        authorized_service_ids=("svc-gateway",),
        environment="lab",
        window_start=now - timedelta(minutes=10),
        window_end=now,
        observation_cutoff=now,
        snapshot_id="cap-test-00000000",
    )
    cases = [
        (
            ToolRequest(
                tool=ToolName.RESOLVE_SERVICE,
                arguments={"name": "gateway", "environment": "production"},
                reason="Attempt an environment change.",
            ),
            "environment",
        ),
        (
            ToolRequest(
                tool=ToolName.GET_METRICS,
                arguments={
                    "service_id": "svc-gateway",
                    "template": "request_latency",
                    "window_start": now - timedelta(minutes=11),
                    "window_end": now,
                },
                reason="Attempt a wider time range.",
            ),
            "authorized observation interval",
        ),
        (
            ToolRequest(
                tool=ToolName.GET_SERVICE_CONTEXT,
                arguments={
                    "service_id": "svc-gateway",
                    "observation_time": now + timedelta(seconds=1),
                },
                reason="Attempt a future topology lookup.",
            ),
            "exceeds the cutoff",
        ),
        (
            ToolRequest(
                tool=ToolName.RETRIEVE_RUNBOOKS,
                arguments={
                    "query": "Find a gateway runbook",
                    "service_ids": ["svc-gateway"],
                    "cutoff": now - timedelta(seconds=1),
                },
                reason="Attempt a mutable retrieval cutoff.",
            ),
            "immutable observation cutoff",
        ),
    ]
    for request, message in cases:
        with pytest.raises(PolicyViolation, match=message):
            validate_tool_request(request, runtime, [])


def test_report_citation_policy_covers_support_execution_and_abstention() -> None:
    now = datetime(2026, 9, 23, 12, tzinfo=UTC)
    item = evidence()
    unsupported = RankedHypothesis(
        rank=1,
        mechanism="dependency failure",
        suspected_component="svc-payments",
        evidence_strength="low",
        supporting_evidence_ids=[],
        explanation_summary="A deliberately unsupported test hypothesis.",
    )
    executed = RecommendedNextStep.model_construct(
        description="Restart the dependency.",
        rationale="Exercise the no-execution policy.",
        evidence_ids=[item.evidence_id],
        risk_level="high",
        preconditions=[],
        verification_steps=[],
        rollback_considerations=[],
        execution_status="executed",
    )
    base = InvestigationReport(
        investigation_id=uuid4(),
        report_version=1,
        mode="replay",
        snapshot_id="cap-test-00000000",
        target_service="svc-gateway",
        environment="lab",
        incident_window=IncidentWindow(start=now - timedelta(minutes=5), end=now),
        observation_cutoff=now,
        outcome="probable_cause",
        summary="A report used to exercise citation policy branches.",
        ranked_hypotheses=[unsupported],
        recommended_next_steps=[executed],
        limitations=["Test fixture."],
        termination_reason="test",
        usage_and_timing=UsageAndTiming(
            model_calls=0,
            tool_calls=0,
            input_tokens=0,
            output_tokens=0,
            estimated_cost_usd=0,
            active_duration_ms=0,
            model_latency_ms=0,
            tool_latency_ms=0,
        ),
        trace_reference="trace://test",
    )
    errors = validate_report_citations(base, [item])
    assert "no supporting evidence" in errors[0]
    assert "not_executed" in errors[1]

    inconclusive = base.model_copy(update={"outcome": ReportOutcome.INCONCLUSIVE})
    errors = validate_report_citations(inconclusive, [item])
    assert any("additional evidence" in message for message in errors)
