from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest

from incidentgraph.api import create_app
from incidentgraph.auth import hash_token
from incidentgraph.config import Settings
from incidentgraph.investigation_tools import CaptureToolbox
from incidentgraph.investigator import (
    Counters,
    ModelResult,
    ModelUsage,
    PlanDecision,
    ToolName,
    ToolRequest,
    ToolRuntimeContext,
    _model_call,
)
from incidentgraph.observability import (
    configure_observability,
    parent_context,
    tracer,
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


@pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION") != "1",
    reason="real services not enabled",
)
async def test_correlated_trace_retention_and_fail_closed_tool(tmp_path: Path) -> None:
    token = "phase8-owner-token"
    settings = Settings(  # type: ignore[call-arg]
        environment="test",
        auth_tokens_json=json.dumps(
            {
                hash_token(token): {
                    "principal_id": "phase8-owner",
                    "roles": ["viewer"],
                    "service_ids": ["svc-gateway"],
                }
            }
        ),
        model_provider="local_openai_compatible",
        model_id="phase8-deterministic-never-invoked",
        model_base_url="http://127.0.0.1:11434/v1",
        model_cost_ceiling_usd=0,
        observability_tracing_enabled=True,
        observability_trace_dir=tmp_path,
    )
    database = Database(settings.app_database_dsn.get_secret_value())
    await database.open()
    investigation_id: UUID | None = None
    try:
        await _migrate(database)
        app = create_app(settings)
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                now = datetime.now(UTC)
                response = await client.post(
                    "/api/v1/investigations",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Idempotency-Key": f"phase8-{uuid4()}",
                    },
                    json={
                        "question": "Trace this bounded deterministic security probe.",
                        "target_service": "gateway",
                        "environment": "lab",
                        "window_start": (now - timedelta(minutes=5)).isoformat(),
                        "window_end": now.isoformat(),
                        "mode": "replay",
                    },
                )
                assert response.status_code == 202
                investigation_id = UUID(response.json()["investigation_id"])

        lease = await database.claim_job(
            "phase8-observability-worker", 30, investigation_id=investigation_id
        )
        assert lease is not None
        stored = await database.get_execution_context(lease)
        assert stored["traceparent"]

        configure_observability(settings, "incidentgraph-worker")
        with tracer().start_as_current_span(
            "incidentgraph.worker.attempt",
            context=parent_context(stored["traceparent"]),
            attributes={"incidentgraph.job.task_kind": "investigation"},
        ):
            state: dict[str, Any] = {
                "started_at": now.isoformat(),
                "counters": Counters().model_dump(mode="json"),
            }

            async def deterministic_plan(_: str) -> ModelResult:
                return ModelResult(
                    PlanDecision(
                        action="clarify",
                        objective="Request a bounded missing input.",
                        decision_summary="No external instruction is trusted.",
                    ),
                    ModelUsage(input_tokens=8, output_tokens=6),
                )

            await _model_call(state, settings, deterministic_plan, PlanDecision)
            tool_result = await CaptureToolbox(settings).execute(
                ToolRequest(
                    tool=ToolName.GET_METRICS,
                    arguments={
                        "service_id": "svc-gateway",
                        "template": "request_latency",
                        "window_start": (now - timedelta(minutes=5)).isoformat(),
                        "window_end": now.isoformat(),
                        "resolution_seconds": 1,
                    },
                    reason="Exercise the fail-closed missing snapshot path.",
                ),
                ToolRuntimeContext(
                    investigation_id=investigation_id,
                    principal_id="phase8-owner",
                    authorized_service_ids=("svc-gateway",),
                    environment="lab",
                    window_start=now - timedelta(minutes=5),
                    window_end=now,
                    observation_cutoff=now,
                    snapshot_id="cap-does-not-exist-phase8",
                ),
            )
            assert tool_result.status == "error"
            assert tool_result.error_code == "NOT_FOUND"

        async with database.pool.connection() as connection:
            await connection.execute(
                """
                UPDATE incidentgraph_app.events
                SET created_at = now() - interval '40 days'
                WHERE investigation_id = %s
                """,
                (investigation_id,),
            )
        preview = await database.event_retention_status(30, investigation_id)
        assert preview["expired_count"] >= 1
        assert await database.prune_event_history(30, investigation_id) >= 1

        records: list[dict[str, Any]] = []
        for path in tmp_path.glob("*.jsonl"):  # noqa: ASYNC240
            records.extend(json.loads(line) for line in path.read_text().splitlines())
        names = {record["name"] for record in records}
        assert {
            "incidentgraph.api.request",
            "incidentgraph.worker.attempt",
            "incidentgraph.model.call",
            "incidentgraph.tool.call",
        }.issubset(names)
        relevant = [
            record
            for record in records
            if record["name"]
            in {
                "incidentgraph.api.request",
                "incidentgraph.worker.attempt",
                "incidentgraph.model.call",
                "incidentgraph.tool.call",
            }
        ]
        assert len({record["trace_id"] for record in relevant}) == 1
        rendered = json.dumps(relevant)
        assert token not in rendered
        assert "Authorization" not in rendered
    finally:
        if investigation_id is not None:
            async with database.pool.connection() as connection:
                await connection.execute(
                    "DELETE FROM incidentgraph_app.investigations WHERE id = %s",
                    (investigation_id,),
                )
        await database.close()
