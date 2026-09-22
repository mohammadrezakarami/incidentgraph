from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from incidentgraph.config import Settings
from incidentgraph.models import InvestigationCreate
from incidentgraph.persistence import Database, LeaseLostError

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION") != "1",
    reason="real services not enabled",
)
async def test_expired_worker_lease_is_reclaimed_without_duplicate_completion() -> None:
    settings = Settings()  # type: ignore[call-arg]
    database = Database(settings.app_database_dsn.get_secret_value())
    await database.open()
    try:
        await database.apply_migration(Path("ops/migrations/001_app.sql"))
        now = datetime.now(UTC)
        accepted = await database.create_investigation(
            owner_id="integration-user",
            request_id=uuid4(),
            idempotency_key=f"restart-{uuid4()}",
            request=InvestigationCreate(
                question="Verify that an expired worker lease can be recovered safely.",
                target_service="gateway",
                window_start=now - timedelta(minutes=5),
                window_end=now,
                mode="replay",
            ),
        )

        stale = await database.claim_job("crashed-worker", lease_seconds=2)
        assert stale is not None
        await asyncio.sleep(2.2)

        recovered = await database.claim_job("recovery-worker", lease_seconds=10)
        assert recovered is not None
        assert recovered.investigation_id == accepted.investigation_id
        assert recovered.attempt == 2
        await database.complete_job(recovered)

        with pytest.raises(LeaseLostError):
            await database.complete_job(stale)

        events = await database.list_events(accepted.investigation_id, "integration-user")
        assert [event.kind for event in events].count("job.completed") == 1
    finally:
        await database.close()
