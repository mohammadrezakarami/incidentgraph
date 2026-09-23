"""Publish, resume, or remove a deterministic Phase 7 browser-test investigation."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
from uuid import UUID, uuid4

from incidentgraph.config import Settings
from incidentgraph.models import (
    EvidenceItem,
    EvidenceStrength,
    ImpactStatement,
    IncidentWindow,
    InvestigationReport,
    RankedHypothesis,
    RecommendedNextStep,
    ReportOutcome,
    UsageAndTiming,
)
from incidentgraph.persistence import Database

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)


async def publish(database: Database, investigation_id: UUID) -> None:
    record = await database.get_investigation(investigation_id, "phase7-e2e-owner")
    if record is None:
        raise RuntimeError("browser fixture investigation not found")
    lease = await database.claim_job(
        "phase7-e2e-fixture-worker", 30, investigation_id=investigation_id
    )
    if lease is None:
        raise RuntimeError("browser fixture could not lease the queued investigation")
    content = json.dumps(
        {
            "template": "request_latency",
            "series": [
                {
                    "template_source": "request_latency",
                    "metric": {"service": "gateway", "quantile": "0.95"},
                    "values": [
                        [record.window_start.timestamp(), "0.12"],
                        [record.window_end.timestamp(), "0.88"],
                    ],
                }
            ],
        },
        sort_keys=True,
    )
    evidence = EvidenceItem(
        evidence_id=uuid4(),
        kind="metric",
        source_id="phase7-e2e-metric",
        source_version="1",
        service_ids=["svc-gateway"],
        environment="lab",
        observed_at=record.window_end,
        collected_at=record.window_end,
        content_hash=hashlib.sha256(content.encode()).hexdigest(),
        freshness_status="fresh",
        limitations=["Deterministic Playwright fixture; not an AI benchmark result."],
        provenance_reference="fixture://phase7/playwright/metric",
        window_start=record.window_start,
        window_end=record.window_end,
        valid_from=record.window_start,
        snapshot_id="phase7-e2e-snapshot",
        query_template_id="phase7-e2e-request-latency",
        safe_parameters={"service_ids": ["svc-gateway"]},
        content=content,
        unit="seconds",
        aggregation="captured p95 range values",
    )
    await database.persist_evidence(investigation_id, [evidence])
    await database.append_investigation_event(
        investigation_id,
        "tool.completed",
        {
            "tool": "get_metrics",
            "duration_ms": 3.7,
            "outcome": "ok",
            "summary": "returned a deterministic bounded browser-test metric",
            "evidence_ids": [str(evidence.evidence_id)],
        },
        deduplication_key="phase7-e2e-tool",
    )
    report = InvestigationReport(
        investigation_id=investigation_id,
        report_version=1,
        mode=record.mode,
        snapshot_id="phase7-e2e-snapshot",
        target_service=record.target_service,
        environment=record.environment,
        incident_window=IncidentWindow(start=record.window_start, end=record.window_end),
        observation_cutoff=record.window_end,
        outcome=ReportOutcome.PROBABLE_CAUSE,
        summary="The browser fixture report is grounded in the API-served latency record.",
        observed_symptoms=[
            ImpactStatement(
                description="The captured gateway p95 latency increased inside the window.",
                evidence_ids=[evidence.evidence_id],
            )
        ],
        ranked_hypotheses=[
            RankedHypothesis(
                rank=1,
                mechanism="Gateway latency rose within the selected observation window",
                suspected_component="svc-gateway",
                evidence_strength=EvidenceStrength.MEDIUM,
                supporting_evidence_ids=[evidence.evidence_id],
                explanation_summary="The cited range series rises from 0.12 to 0.88 seconds.",
                additional_evidence_needed=["Correlate downstream latency before remediation."],
            )
        ],
        observed_impact=[
            ImpactStatement(
                description="Gateway responses were slower in the bounded fixture window.",
                evidence_ids=[evidence.evidence_id],
            )
        ],
        recommended_next_steps=[
            RecommendedNextStep(
                description="Inspect bounded downstream timing without changing infrastructure.",
                rationale="A second independent observation would strengthen the diagnosis.",
                evidence_ids=[evidence.evidence_id],
                risk_level="low",
                preconditions=["Keep the investigation read-only."],
                verification_steps=["Compare the same immutable observation window."],
                rollback_considerations=["No operational change is performed."],
            )
        ],
        limitations=["Deterministic Playwright fixture; not an AI benchmark result."],
        termination_reason="phase7_e2e_fixture",
        usage_and_timing=UsageAndTiming(
            model_calls=0,
            tool_calls=1,
            input_tokens=0,
            output_tokens=0,
            estimated_cost_usd=0,
            active_duration_ms=5,
            model_latency_ms=0,
            tool_latency_ms=3.7,
        ),
        trace_reference=f"trace://phase7-e2e/{investigation_id}",
    )
    await database.publish_report_under_lease(
        lease,
        report,
        publication_key="phase7-e2e-report-v1",
        require_review=True,
        review_ttl_seconds=300,
        evidence_summary=[{"evidence_id": str(evidence.evidence_id), "kind": "metric"}],
        uncertainties=report.limitations,
    )


async def resume(database: Database, investigation_id: UUID) -> None:
    lease = await database.claim_job(
        "phase7-e2e-review-resumer", 30, investigation_id=investigation_id
    )
    if lease is None or lease.task_kind != "review_resume":
        raise RuntimeError("accepted review resume was not queued")
    await database.complete_review_resume(lease)


async def cleanup(database: Database, investigation_id: UUID) -> None:
    async with database.pool.connection() as connection:
        await connection.execute(
            "DELETE FROM incidentgraph_app.investigations WHERE id = %s",
            (investigation_id,),
        )


async def run(action: str, investigation_id: UUID) -> None:
    settings = Settings()  # type: ignore[call-arg]
    database = Database(settings.app_database_dsn.get_secret_value())
    await database.open()
    try:
        if action == "publish":
            await publish(database, investigation_id)
        elif action == "resume":
            await resume(database, investigation_id)
        else:
            await cleanup(database, investigation_id)
    finally:
        await database.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("publish", "resume", "cleanup"))
    parser.add_argument("investigation_id", type=UUID)
    arguments = parser.parse_args()
    asyncio.run(run(arguments.action, arguments.investigation_id))


if __name__ == "__main__":
    main()
