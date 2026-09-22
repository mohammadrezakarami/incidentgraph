from __future__ import annotations

import asyncio

import structlog

from incidentgraph.config import Settings
from incidentgraph.logging import configure_logging
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
    await database.complete_job(lease)
    log.info("non_ai_test_job_completed")
    return True


async def run_worker_once(settings: Settings) -> bool:
    database = Database(settings.app_database_dsn.get_secret_value())
    await database.open()
    try:
        return await process_one(database, settings.worker_id, settings.worker_lease_seconds)
    finally:
        await database.close()


def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    configure_logging(settings.log_level)
    processed = asyncio.run(run_worker_once(settings))
    raise SystemExit(0 if processed else 2)
