from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest

from incidentgraph.api import create_app
from incidentgraph.auth import hash_token
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

pytestmark = pytest.mark.integration


async def _migrate(database: Database) -> None:
    for name in (
        "001_app.sql",
        "002_agent.sql",
        "003_durability.sql",
        "004_observability.sql",
    ):
        await database.apply_migration(Path("ops/migrations") / name)


def _capture(root: Path, start: datetime, end: datetime) -> str:
    snapshot_id = "cap-phase7-api-00000001"
    directory = root / snapshot_id
    directory.mkdir(parents=True)
    (directory / "manifest.json").write_text(
        json.dumps(
            {
                "observation_start": start.isoformat(),
                "observation_cutoff": end.isoformat(),
                "services": ["gateway", "checkout", "payments"],
                "provenance_category": "test_capture",
                "limitations": ["integration test"],
            }
        ),
        encoding="utf-8",
    )
    return snapshot_id


@pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION") != "1",
    reason="real services not enabled",
)
async def test_real_api_report_evidence_sse_and_cross_user_boundaries(tmp_path: Path) -> None:
    owner_token = "phase7-owner-token"
    other_token = "phase7-other-token"
    operator_token = "phase7-operator-token"
    settings = Settings(  # type: ignore[call-arg]
        environment="test",
        auth_tokens_json=json.dumps(
            {
                hash_token(owner_token): {
                    "principal_id": "phase7-owner",
                    "roles": ["viewer", "reviewer"],
                    "service_ids": ["svc-gateway", "svc-checkout", "svc-payments"],
                },
                hash_token(other_token): {
                    "principal_id": "phase7-other",
                    "roles": ["viewer", "reviewer"],
                    "service_ids": ["svc-gateway", "svc-checkout", "svc-payments"],
                },
                hash_token(operator_token): {
                    "principal_id": "phase7-operator",
                    "roles": ["operator"],
                    "service_ids": ["svc-gateway", "svc-checkout", "svc-payments"],
                },
            }
        ),
        model_provider="local_openai_compatible",
        model_id="phase7-never-invoked",
        model_base_url="http://127.0.0.1:11434/v1",
        model_cost_ceiling_usd=0,
    )
    database = Database(settings.app_database_dsn.get_secret_value())
    await database.open()
    investigation_id: UUID | None = None
    try:
        await _migrate(database)
        now = datetime.now(UTC)
        start = now - timedelta(minutes=5)
        capture_root = tmp_path / "captures"
        snapshot_id = _capture(capture_root, start, now)
        app = create_app(settings, capture_root=capture_root)
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                owner_headers = {"Authorization": f"Bearer {owner_token}"}
                other_headers = {"Authorization": f"Bearer {other_token}"}
                operator_headers = {"Authorization": f"Bearer {operator_token}"}
                created = await client.post(
                    "/api/v1/investigations",
                    headers={**owner_headers, "Idempotency-Key": f"phase7-{uuid4()}"},
                    json={
                        "question": "Why did gateway latency rise in this bounded replay window?",
                        "target_service": "gateway",
                        "environment": "lab",
                        "window_start": start.isoformat(),
                        "window_end": now.isoformat(),
                        "mode": "replay",
                        "snapshot_id": snapshot_id,
                    },
                )
                assert created.status_code == 202
                investigation_id = UUID(created.json()["investigation_id"])

                lease = await database.claim_job(
                    "phase7-contract-worker", 30, investigation_id=investigation_id
                )
                assert lease is not None
                metric_content = json.dumps(
                    {
                        "template": "request_latency",
                        "series": [
                            {
                                "metric": {"service": "gateway"},
                                "values": [
                                    [now.timestamp() - 60, "0.14"],
                                    [now.timestamp(), "0.91"],
                                ],
                            }
                        ],
                    },
                    sort_keys=True,
                )
                evidence = EvidenceItem(
                    evidence_id=uuid4(),
                    kind="metric",
                    source_id="phase7-contract-metric",
                    source_version="1",
                    service_ids=["svc-gateway"],
                    environment="lab",
                    observed_at=now,
                    collected_at=now,
                    content_hash=hashlib.sha256(metric_content.encode()).hexdigest(),
                    freshness_status="fresh",
                    limitations=["deterministic browser-contract fixture"],
                    provenance_reference="fixture://phase7/metric",
                    window_start=now - timedelta(minutes=5),
                    window_end=now,
                    valid_from=now - timedelta(minutes=5),
                    snapshot_id="phase7-contract-snapshot",
                    query_template_id="phase7-contract-template",
                    content=metric_content,
                    unit="seconds",
                    aggregation="captured range values",
                )
                await database.persist_evidence(investigation_id, [evidence])
                await database.append_investigation_event(
                    investigation_id,
                    "tool.completed",
                    {
                        "tool": "get_metrics",
                        "duration_ms": 4.2,
                        "outcome": "ok",
                        "summary": "returned one bounded metric series",
                    },
                    deduplication_key="phase7-contract-tool",
                )
                report = InvestigationReport(
                    investigation_id=investigation_id,
                    report_version=1,
                    mode="replay",
                    snapshot_id="phase7-contract-snapshot",
                    target_service="svc-gateway",
                    environment="lab",
                    incident_window=IncidentWindow(start=now - timedelta(minutes=5), end=now),
                    observation_cutoff=now,
                    outcome=ReportOutcome.PROBABLE_CAUSE,
                    summary="Gateway latency rose alongside the cited bounded metric observation.",
                    observed_symptoms=[
                        ImpactStatement(
                            description="Gateway request latency increased.",
                            evidence_ids=[evidence.evidence_id],
                        )
                    ],
                    ranked_hypotheses=[
                        RankedHypothesis(
                            rank=1,
                            mechanism="Bounded gateway latency increase",
                            suspected_component="svc-gateway",
                            evidence_strength=EvidenceStrength.MEDIUM,
                            supporting_evidence_ids=[evidence.evidence_id],
                            explanation_summary="The metric rises inside the selected window.",
                            additional_evidence_needed=["Correlated downstream timing."],
                        )
                    ],
                    observed_impact=[
                        ImpactStatement(
                            description="Requests experienced increased response time.",
                            evidence_ids=[evidence.evidence_id],
                        )
                    ],
                    recommended_next_steps=[
                        RecommendedNextStep(
                            description="Inspect downstream latency without making changes.",
                            rationale="A second signal is needed before stronger causal language.",
                            evidence_ids=[evidence.evidence_id],
                            risk_level="low",
                            verification_steps=["Compare bounded dependency latency."],
                        )
                    ],
                    limitations=["Laboratory fixture, not production evidence."],
                    termination_reason="phase7_contract_fixture",
                    usage_and_timing=UsageAndTiming(
                        model_calls=0,
                        tool_calls=1,
                        input_tokens=0,
                        output_tokens=0,
                        estimated_cost_usd=0,
                        active_duration_ms=5,
                        model_latency_ms=0,
                        tool_latency_ms=4.2,
                    ),
                    trace_reference=f"trace://phase7/{investigation_id}",
                )
                await database.publish_report_under_lease(
                    lease,
                    report,
                    publication_key="phase7-contract-report-v1",
                    require_review=False,
                    review_ttl_seconds=60,
                )

                owner_record = await client.get(
                    f"/api/v1/investigations/{investigation_id}", headers=owner_headers
                )
                owner_report = await client.get(
                    f"/api/v1/investigations/{investigation_id}/report", headers=owner_headers
                )
                owner_evidence = await client.get(
                    f"/api/v1/investigations/{investigation_id}/evidence/{evidence.evidence_id}",
                    headers=owner_headers,
                )
                resumed_events = await client.get(
                    f"/api/v1/investigations/{investigation_id}/events",
                    headers={**owner_headers, "Last-Event-ID": "1"},
                )
                assert owner_record.status_code == 200
                assert owner_report.json()["report"]["summary"] == report.summary
                assert owner_evidence.json()["evidence_id"] == str(evidence.evidence_id)
                assert "id: 1\n" not in resumed_events.text
                assert "tool.completed" in resumed_events.text

                for path in (
                    f"/api/v1/investigations/{investigation_id}",
                    f"/api/v1/investigations/{investigation_id}/report",
                    f"/api/v1/investigations/{investigation_id}/evidence/{evidence.evidence_id}",
                    f"/api/v1/investigations/{investigation_id}/events",
                ):
                    assert (await client.get(path, headers=other_headers)).status_code == 404
                other_list = await client.get("/api/v1/investigations", headers=other_headers)
                assert all(
                    item["investigation_id"] != str(investigation_id)
                    for item in other_list.json()["items"]
                )
                denied_review = await client.post(
                    f"/api/v1/investigations/{investigation_id}/reviews",
                    headers={**other_headers, "Idempotency-Key": "cross-user-review"},
                    json={
                        "report_version": 1,
                        "decision": "accept",
                        "rationale": "Must not cross the ownership boundary.",
                    },
                )
                assert denied_review.status_code == 404
                assert (
                    await client.get(
                        f"/api/v1/investigations/{investigation_id}",
                        headers=operator_headers,
                    )
                ).status_code == 200
    finally:
        if investigation_id is not None:
            async with database.pool.connection() as connection:
                await connection.execute(
                    "DELETE FROM incidentgraph_app.investigations WHERE id = %s",
                    (investigation_id,),
                )
        await database.close()
