from __future__ import annotations

import json
from typing import Any

from incidentgraph.config import Settings
from incidentgraph.investigation_tools import CaptureToolbox
from incidentgraph.investigator import ModelResult, ModelUsage, ToolName, ToolResult
from incidentgraph.phase9_v2_evaluation import ObservationPlan
from incidentgraph.phase9_v3_dataset import CAPTURE_ROOT, CASE_PATH
from incidentgraph.phase9_v4_evaluation import run_adaptive_case, run_fixed_case


def settings() -> Settings:
    return Settings(
        environment="test",
        app_database_dsn="postgresql://app:test@localhost/app",
        lab_database_dsn="postgresql://lab:test@localhost/lab",
        neo4j_uri="bolt://localhost:7687",
        neo4j_password="test-only-password",
        auth_tokens_json="{}",
    )


def development_case(case_id: str = "incident-v3-dev-016") -> dict[str, Any]:
    return next(
        item
        for item in map(json.loads, CASE_PATH.read_text().splitlines())
        if item["case_id"] == case_id
    )


class CaptureOnlyToolbox(CaptureToolbox):
    def _retrieve(self, tool: ToolName, value: Any, context: Any) -> ToolResult:
        del value, context
        return ToolResult(
            tool=tool,
            status="error",
            summary="retrieval is deliberately offline in this workflow contract test",
            error_code="UNAVAILABLE",
        )


class ContextFirstPlanner:
    def __init__(self) -> None:
        self.calls = 0

    async def plan(self, context: str) -> ModelResult:
        self.calls += 1
        payload = json.loads(context)
        assert payload["remaining_observation_bundles"] == [
            "resource_signals",
            "context_signals",
        ]
        return ModelResult(
            ObservationPlan(
                action="observe",
                bundle="context_signals",
                decision_summary="Inspect bounded context signals first.",
            ),
            ModelUsage(input_tokens=21, output_tokens=7, latency_ms=3),
        )


class EarlyFinishPlanner:
    async def plan(self, context: str) -> ModelResult:
        del context
        return ModelResult(
            ObservationPlan(
                action="finish",
                bundle=None,
                decision_summary="Attempt an unsafe early finish.",
            ),
            ModelUsage(input_tokens=13, output_tokens=5, latency_ms=2),
        )


async def test_fixed_and_adaptive_share_complete_access_and_policy_outcome() -> None:
    case = development_case()
    configured = settings()
    fixed_tools = CaptureOnlyToolbox(configured, CAPTURE_ROOT)
    adaptive_tools = CaptureOnlyToolbox(configured, CAPTURE_ROOT)
    planner = ContextFirstPlanner()

    fixed = await run_fixed_case(
        case,
        configured,
        source_job_id="contract-fixed-cpu",
        toolbox=fixed_tools,
    )
    adaptive = await run_adaptive_case(
        case,
        configured,
        planner,
        source_job_id="contract-adaptive-cpu",
        toolbox=adaptive_tools,
    )

    assert planner.calls == 1
    assert fixed["report_valid"] is adaptive["report_valid"] is True
    assert fixed["report"]["ranked_hypotheses"][0]["mechanism"] == "cpu_contention"
    assert adaptive["report"]["ranked_hypotheses"][0]["mechanism"] == "cpu_contention"
    assert fixed["selected_fact_refs"] == adaptive["selected_fact_refs"] == ["F12"]
    assert fixed["counters"]["tool_calls"] == adaptive["counters"]["tool_calls"] == 14
    assert fixed["counters"]["model_calls"] == 0
    assert adaptive["counters"]["model_calls"] == 1
    assert adaptive["counters"]["input_tokens"] == 21
    assert adaptive["counters"]["output_tokens"] == 7
    assert adaptive["counters"]["model_latency_ms"] == 3

    for result in (fixed, adaptive):
        report = result["report"]
        cited = {
            evidence_id
            for hypothesis in report["ranked_hypotheses"]
            for evidence_id in hypothesis["supporting_evidence_ids"]
        }
        cited.update(
            evidence_id
            for symptom in report["observed_symptoms"]
            for evidence_id in symptom["evidence_ids"]
        )
        assert cited.issubset(set(result["evidence_ids"]))
        assert result["derived_policy_evidence"]["evidence_id"] in result["evidence_ids"]
        assert report["target_service"] == "svc-payments"
        assert report["usage_and_timing"]["tool_calls"] == 14
        assert "phase9-v4-repair3-workflow-v1" in report["trace_reference"]


async def test_adaptive_early_finish_is_rejected_without_second_model_call() -> None:
    case = development_case("incident-v3-dev-013")
    configured = settings()
    result = await run_adaptive_case(
        case,
        configured,
        EarlyFinishPlanner(),
        toolbox=CaptureOnlyToolbox(configured, CAPTURE_ROOT),
    )

    assert result["report_valid"] is True
    assert result["report"]["ranked_hypotheses"][0]["mechanism"] == "deployment_regression"
    assert result["counters"]["model_calls"] == 1
    assert result["counters"]["tool_calls"] == 14
    assert result["selected_fact_refs"] == ["F1", "F13"]
    assert any("Early finish rejected" in item for item in result["decision_summaries"])
