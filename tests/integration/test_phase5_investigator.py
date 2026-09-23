from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest

from incidentgraph.config import Settings
from incidentgraph.investigation_tools import CaptureToolbox
from incidentgraph.investigator import (
    HypothesisRevision,
    ModelResult,
    ModelUsage,
    PlanDecision,
    ReportDraft,
    ToolName,
    ToolRequest,
    ToolResult,
    ToolRuntimeContext,
    initial_state,
    persistent_workflow,
)
from incidentgraph.models import (
    EvidenceItem,
    ImpactStatement,
    InvestigationCreate,
    InvestigationMode,
    RankedHypothesis,
)
from incidentgraph.persistence import Database

pytestmark = [pytest.mark.integration, pytest.mark.investigator_integration]


class CheckpointTools:
    def __init__(self) -> None:
        now = datetime(2026, 9, 23, 12, tzinfo=UTC)
        self.item = EvidenceItem(
            evidence_id=uuid5(NAMESPACE_URL, "phase5-checkpoint-evidence"),
            kind="log",
            source_id="integration-log",
            source_version="1",
            service_ids=["svc-gateway"],
            environment="lab",
            observed_at=now,
            collected_at=now,
            content_hash="b" * 64,
            freshness_status="fresh",
            provenance_reference="integration://phase5/log",
            content="bounded integration evidence",
        )

    async def execute(self, request: ToolRequest, context: ToolRuntimeContext) -> ToolResult:
        del context
        if request.tool == ToolName.RESOLVE_SERVICE:
            return ToolResult(
                tool=request.tool,
                status="ok",
                summary="resolved",
                data={"service_id": "svc-gateway"},
            )
        return ToolResult(
            tool=request.tool,
            status="ok",
            summary="returned one event",
            evidence=(self.item,),
            data={"events": [{"status_code": 502}]},
        )


class CheckpointModel:
    def __init__(self, item: EvidenceItem) -> None:
        self.item = item

    async def plan(self, context: str) -> ModelResult:
        state = json.loads(context)
        start, end = state["window"]
        return ModelResult(
            PlanDecision(
                action="observe",
                objective="Inspect request errors.",
                decision_summary="Logs are the most direct next observation.",
                tool_request=ToolRequest(
                    tool="search_logs",
                    arguments={
                        "service_ids": ["svc-gateway"],
                        "window_start": start,
                        "window_end": end,
                        "limit": 20,
                    },
                    reason="Inspect bounded error events.",
                ),
            ),
            ModelUsage(input_tokens=20, output_tokens=10, latency_ms=1),
        )

    async def update_hypotheses(self, context: str) -> ModelResult:
        del context
        return ModelResult(
            HypothesisRevision(
                hypotheses=[
                    RankedHypothesis(
                        rank=1,
                        mechanism="upstream request failures",
                        suspected_component="svc-gateway",
                        evidence_strength="medium",
                        supporting_evidence_ids=[self.item.evidence_id],
                        explanation_summary="The event records a failed request.",
                    )
                ],
                sufficient=True,
                decision_summary="A bounded report can be drafted.",
            ),
            ModelUsage(input_tokens=20, output_tokens=10, latency_ms=1),
        )

    async def draft_report(self, context: str) -> ModelResult:
        del context
        return ModelResult(
            ReportDraft(
                outcome="probable_cause",
                summary="Gateway request failures are present in the observed evidence.",
                observed_symptoms=[
                    ImpactStatement(
                        description="A gateway request returned an error.",
                        evidence_ids=[self.item.evidence_id],
                    )
                ],
                ranked_hypotheses=[
                    RankedHypothesis(
                        rank=1,
                        mechanism="upstream request failures",
                        suspected_component="svc-gateway",
                        evidence_strength="medium",
                        supporting_evidence_ids=[self.item.evidence_id],
                        explanation_summary="The event records a failed request.",
                    )
                ],
                limitations=["Integration fixture, not production evidence."],
            ),
            ModelUsage(input_tokens=20, output_tokens=10, latency_ms=1),
        )


@pytest.mark.skipif(
    os.getenv("RUN_INVESTIGATOR_INTEGRATION") != "1",
    reason="Phase 5 investigator integration is not enabled",
)
async def test_postgres_checkpointer_persists_completed_workflow_state() -> None:
    settings = Settings()  # type: ignore[call-arg]
    tools = CheckpointTools()
    model = CheckpointModel(tools.item)
    request_id = uuid4()
    end = datetime(2026, 9, 23, 12, tzinfo=UTC)
    database = Database(settings.app_database_dsn.get_secret_value())
    await database.open()
    try:
        accepted = await database.create_investigation(
            owner_id="integration-viewer",
            request_id=request_id,
            idempotency_key=f"phase5-{request_id}",
            request=InvestigationCreate(
                question="Why did gateway requests fail?",
                target_service="gateway",
                environment="lab",
                window_start=datetime(2026, 9, 23, 11, 55, tzinfo=UTC),
                window_end=end,
                mode=InvestigationMode.REPLAY,
            ),
        )
    finally:
        await database.close()
    investigation_id = accepted.investigation_id
    initial = initial_state(
        investigation_id=investigation_id,
        request_id=request_id,
        principal_id="integration-viewer",
        authorized_service_ids=("svc-gateway", "svc-checkout", "svc-payments"),
        question="Why did gateway requests fail?",
        target_service="gateway",
        window_start=datetime(2026, 9, 23, 11, 55, tzinfo=UTC),
        window_end=end,
        observation_cutoff=end,
        mode=InvestigationMode.REPLAY,
        snapshot_id="cap-integration-0001",
        corpus_version="integration-corpus-v1",
    )
    config: dict[str, Any] = {"configurable": {"thread_id": initial["thread_id"]}}

    async with persistent_workflow(settings, model, tools, setup=True) as workflow:
        result = await workflow.ainvoke(initial, config=config)
        saved = await workflow.aget_state(config)

    assert result["status"] == "completed"
    assert saved.values["status"] == "completed"
    assert saved.values["report_valid"] is True
    assert saved.values["counters"]["model_calls"] == 3
    assert saved.values["evidence"][0]["content"] is None
    database = Database(settings.app_database_dsn.get_secret_value())
    await database.open()
    try:
        persisted_evidence = await database.get_evidence(
            investigation_id, tools.item.evidence_id
        )
        persisted_report = await database.get_report(investigation_id, 1)
    finally:
        await database.close()
    assert persisted_evidence is not None
    assert persisted_evidence.content == "bounded integration evidence"
    assert persisted_report is not None
    assert persisted_report.outcome.value == "probable_cause"


@pytest.mark.skipif(
    os.getenv("RUN_INVESTIGATOR_INTEGRATION") != "1",
    reason="Phase 5 investigator integration is not enabled",
)
async def test_capture_tools_return_bounded_metric_log_and_change_evidence() -> None:
    settings = Settings()  # type: ignore[call-arg]
    toolbox = CaptureToolbox(settings)
    capture_id = "cap-20260922214713-1d16da3def"
    start = datetime(2026, 9, 22, 21, 47, 13, 471515, tzinfo=UTC)
    end = datetime(2026, 9, 22, 21, 47, 20, 416585, tzinfo=UTC)
    context = ToolRuntimeContext(
        investigation_id=uuid4(),
        principal_id="integration-viewer",
        authorized_service_ids=("svc-gateway", "svc-checkout", "svc-payments"),
        environment="lab",
        window_start=start,
        window_end=end,
        observation_cutoff=end,
        snapshot_id=capture_id,
    )
    requests = [
        ToolRequest(
            tool="get_metrics",
            arguments={
                "service_id": "svc-gateway",
                "template": "request_latency",
                "window_start": start.isoformat(),
                "window_end": end.isoformat(),
                "resolution_seconds": 1,
            },
            reason="Inspect request latency.",
        ),
        ToolRequest(
            tool="search_logs",
            arguments={
                "service_ids": ["svc-gateway"],
                "window_start": start.isoformat(),
                "window_end": end.isoformat(),
                "limit": 10,
            },
            reason="Inspect bounded gateway logs.",
        ),
        ToolRequest(
            tool="get_recent_changes",
            arguments={
                "service_ids": ["svc-checkout"],
                "window_start": start.isoformat(),
                "window_end": end.isoformat(),
            },
            reason="Inspect approved changes.",
        ),
    ]

    results = [await toolbox.execute(request, context) for request in requests]

    assert all(result.status == "ok" for result in results)
    assert all(result.evidence for result in results)
    assert results[1].data["event_count"] <= 10
    assert results[2].data["changes"][0]["version"] == "v1.1.0-regressed"
