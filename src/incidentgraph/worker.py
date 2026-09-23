from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, cast
from uuid import UUID

import structlog

from incidentgraph.config import Settings
from incidentgraph.durability import DurableWorkflowCoordinator
from incidentgraph.investigation_tools import CaptureToolbox
from incidentgraph.investigator import (
    OpenAIInvestigatorModel,
    initial_state,
    persistent_workflow,
)
from incidentgraph.logging import configure_logging
from incidentgraph.models import InvestigationMode
from incidentgraph.persistence import Database


async def process_one(database: Database, worker_id: str, lease_seconds: int) -> bool:
    lease = await database.claim_job(worker_id, lease_seconds)
    if lease is None:
        return False
    log = structlog.get_logger().bind(
        investigation_id=str(lease.investigation_id),
        worker_id=worker_id,
        attempt=lease.attempt,
    )
    log.info("non_ai_test_job_started")
    if await database.acknowledge_cancellation(lease):
        log.info("non_ai_test_job_cancelled")
        return True
    await database.complete_job(lease)
    log.info("non_ai_test_job_completed")
    return True


async def run_worker_once(settings: Settings) -> bool:
    """Run one real investigator attempt; never substitutes a fake model."""
    model = OpenAIInvestigatorModel(settings)
    tools = CaptureToolbox(settings)
    database = Database(settings.app_database_dsn.get_secret_value())
    await database.open()
    try:
        lease = await database.claim_job(settings.worker_id, settings.worker_lease_seconds)
        if lease is None:
            return False
        context = await database.get_execution_context(lease)
        initial: dict[str, Any] | None = None
        if lease.task_kind == "investigation":
            payload = context["input_payload"]
            if not isinstance(payload, dict):
                raise ValueError("initial work item payload is missing")
            required = {
                "request_id",
                "principal_id",
                "authorized_service_ids",
                "question",
                "target_service",
                "window_start",
                "window_end",
                "observation_cutoff",
                "mode",
                "corpus_version",
            }
            missing = sorted(required - payload.keys())
            if missing:
                raise ValueError(f"initial work item is missing: {', '.join(missing)}")
            initial = cast(
                dict[str, Any],
                initial_state(
                    investigation_id=lease.investigation_id,
                    request_id=UUID(str(payload["request_id"])),
                    principal_id=str(payload["principal_id"]),
                    authorized_service_ids=tuple(
                        str(item) for item in payload["authorized_service_ids"]
                    ),
                    question=str(payload["question"]),
                    target_service=str(payload["target_service"]),
                    window_start=datetime.fromisoformat(str(payload["window_start"])),
                    window_end=datetime.fromisoformat(str(payload["window_end"])),
                    observation_cutoff=datetime.fromisoformat(str(payload["observation_cutoff"])),
                    mode=InvestigationMode(str(payload["mode"])),
                    snapshot_id=(
                        str(payload["snapshot_id"])
                        if payload.get("snapshot_id") is not None
                        else None
                    ),
                    corpus_version=str(payload["corpus_version"]),
                ),
            )
        async with persistent_workflow(
            settings,
            model,
            tools,
            defer_report_publication=True,
        ) as workflow:
            coordinator = DurableWorkflowCoordinator(
                database,
                workflow,
                require_review=settings.human_review_required,
                review_ttl_seconds=settings.review_ttl_seconds,
                lease_seconds=settings.worker_lease_seconds,
            )
            await coordinator.process(lease, initial_input=initial)
        return True
    finally:
        await database.close()


def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    configure_logging(settings.log_level)
    processed = asyncio.run(run_worker_once(settings))
    raise SystemExit(0 if processed else 2)
