from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from incidentgraph.config import Settings
from incidentgraph.durability import (
    DurableWorkflowCoordinator,
    authenticated_review_resume,
    versioned_follow_up,
)
from incidentgraph.models import (
    FollowUpCreate,
    IncidentWindow,
    InvestigationCreate,
    InvestigationMode,
    InvestigationReport,
    ReportOutcome,
    ReviewDecision,
    ReviewSubmission,
    UsageAndTiming,
)
from incidentgraph.persistence import (
    CancellationRequestedError,
    Database,
    DurableConflictError,
    LeaseLostError,
    ReviewAuthorizationError,
)

pytestmark = pytest.mark.integration


async def _migrate(database: Database) -> None:
    for name in (
        "001_app.sql",
        "002_agent.sql",
        "003_durability.sql",
        "004_observability.sql",
    ):
        await database.apply_migration(Path("ops/migrations") / name)


async def _delete_investigation(database: Database, investigation_id: object) -> None:
    async with database.pool.connection() as connection:
        await connection.execute(
            "DELETE FROM incidentgraph_app.investigations WHERE id = %s",
            (investigation_id,),
        )


def _report(
    investigation_id: object,
    *,
    version: int,
    now: datetime,
    model_calls: int = 1,
) -> InvestigationReport:
    return InvestigationReport(
        investigation_id=investigation_id,
        report_version=version,
        mode=InvestigationMode.REPLAY,
        snapshot_id="phase6-recovery-test",
        target_service="gateway",
        environment="lab",
        incident_window=IncidentWindow(start=now - timedelta(minutes=5), end=now),
        observation_cutoff=now,
        outcome=ReportOutcome.INCONCLUSIVE,
        summary="The bounded recovery test intentionally makes no causal claim.",
        limitations=["Synthetic Phase 6 durability fixture."],
        termination_reason="durability_test",
        usage_and_timing=UsageAndTiming(
            model_calls=model_calls,
            tool_calls=model_calls,
            input_tokens=10 * model_calls,
            output_tokens=5 * model_calls,
            estimated_cost_usd=0,
            active_duration_ms=10,
            model_latency_ms=5,
            tool_latency_ms=5,
        ),
        trace_reference=f"trace://phase6/{investigation_id}",
    )


@pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION") != "1",
    reason="real services not enabled",
)
async def test_expired_worker_lease_is_reclaimed_without_duplicate_completion() -> None:
    settings = Settings()  # type: ignore[call-arg]
    database = Database(settings.app_database_dsn.get_secret_value())
    await database.open()
    try:
        await _migrate(database)
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

        stale = await database.claim_job(
            "crashed-worker", lease_seconds=2, investigation_id=accepted.investigation_id
        )
        assert stale is not None
        await asyncio.sleep(2.2)

        recovered = await database.claim_job(
            "recovery-worker", lease_seconds=10, investigation_id=accepted.investigation_id
        )
        assert recovered is not None
        assert recovered.investigation_id == accepted.investigation_id
        assert recovered.attempt == 2
        await database.complete_job(recovered)

        with pytest.raises(LeaseLostError):
            await database.complete_job(stale)

        events = await database.list_events(accepted.investigation_id, "integration-user")
        assert [event.kind for event in events].count("job.completed") == 1
    finally:
        if "accepted" in locals():
            await _delete_investigation(database, accepted.investigation_id)
        await database.close()


@pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION") != "1",
    reason="real services not enabled",
)
async def test_review_wait_releases_lease_and_recovery_fences_stale_publication() -> None:
    settings = Settings()  # type: ignore[call-arg]
    database = Database(settings.app_database_dsn.get_secret_value())
    await database.open()
    try:
        await _migrate(database)
        now = datetime.now(UTC)
        accepted = await database.create_investigation(
            owner_id="phase6-review-owner",
            request_id=uuid4(),
            idempotency_key=f"phase6-review-{uuid4()}",
            request=InvestigationCreate(
                question="Can review resume safely after a worker restart?",
                target_service="gateway",
                window_start=now - timedelta(minutes=5),
                window_end=now,
                mode="replay",
            ),
        )
        lease = await database.claim_job(
            "publisher-1", lease_seconds=10, investigation_id=accepted.investigation_id
        )
        assert lease is not None
        assert lease.investigation_id == accepted.investigation_id
        first_report = _report(accepted.investigation_id, version=1, now=now)
        published = await database.publish_report_under_lease(
            lease,
            first_report,
            publication_key="report-v1",
            require_review=True,
            review_ttl_seconds=60,
            evidence_summary=[{"evidence_id": "fixture-1", "kind": "metric"}],
            uncertainties=["Synthetic fixture only."],
        )
        assert published.status == "waiting_for_review"
        duplicate = await database.publish_report_under_lease(
            lease,
            first_report,
            publication_key="report-v1",
            require_review=True,
            review_ttl_seconds=60,
        )
        assert duplicate.duplicate is True
        assert duplicate.review_id == published.review_id

        with pytest.raises(ReviewAuthorizationError):
            await database.submit_review(
                accepted.investigation_id,
                reviewer_id="viewer-1",
                roles=frozenset({"viewer"}),
                idempotency_key="unauthorized-review",
                submission=ReviewSubmission(
                    report_version=1,
                    decision=ReviewDecision.REQUEST_REVISION,
                    rationale="Viewer must not resume a review.",
                ),
            )
        with pytest.raises(DurableConflictError, match="stale"):
            await database.submit_review(
                accepted.investigation_id,
                reviewer_id="reviewer-1",
                roles=frozenset({"reviewer"}),
                idempotency_key="stale-review-v2",
                submission=ReviewSubmission(
                    report_version=2,
                    decision=ReviewDecision.ACCEPT,
                    rationale="This version does not exist.",
                ),
            )

        revision = ReviewSubmission(
            report_version=1,
            decision=ReviewDecision.REQUEST_REVISION,
            rationale="Collect one more bounded observation.",
        )
        decided = await database.submit_review(
            accepted.investigation_id,
            reviewer_id="reviewer-1",
            roles=frozenset({"reviewer"}),
            idempotency_key="revision-decision-1",
            submission=revision,
        )
        repeated = await database.submit_review(
            accepted.investigation_id,
            reviewer_id="reviewer-1",
            roles=frozenset({"reviewer"}),
            idempotency_key="revision-decision-1",
            submission=revision,
        )
        assert repeated == decided

        crashed = await database.claim_job(
            "revision-crashed", lease_seconds=2, investigation_id=accepted.investigation_id
        )
        assert crashed is not None
        assert crashed.task_kind == "review_revision"
        assert crashed.target_report_version == 2
        context = await database.get_execution_context(crashed)
        assert authenticated_review_resume(context).resume["decision"] == "request_revision"
        await asyncio.sleep(2.2)
        recovered = await database.claim_job(
            "revision-recovered", lease_seconds=10, investigation_id=accepted.investigation_id
        )
        assert recovered is not None
        assert recovered.investigation_id == accepted.investigation_id
        assert recovered.attempt == 2
        second_report = _report(
            accepted.investigation_id,
            version=2,
            now=now,
            model_calls=2,
        )
        with pytest.raises(LeaseLostError):
            await database.publish_report_under_lease(
                crashed,
                second_report,
                publication_key="report-v2",
                require_review=True,
                review_ttl_seconds=60,
            )
        await database.publish_report_under_lease(
            recovered,
            second_report,
            publication_key="report-v2",
            require_review=True,
            review_ttl_seconds=60,
        )
        acceptance = ReviewSubmission(
            report_version=2,
            decision=ReviewDecision.ACCEPT,
            rationale="The bounded report is safe to accept.",
        )
        await database.submit_review(
            accepted.investigation_id,
            reviewer_id="reviewer-1",
            roles=frozenset({"reviewer"}),
            idempotency_key="accept-decision-v2",
            submission=acceptance,
        )
        resume = await database.claim_job(
            "accept-resumer", lease_seconds=10, investigation_id=accepted.investigation_id
        )
        assert resume is not None
        assert resume.task_kind == "review_resume"
        assert await database.complete_review_resume(resume) == "inconclusive"

        events = await database.list_events(
            accepted.investigation_id,
            "phase6-review-owner",
        )
        kinds = [event.kind for event in events]
        assert kinds.count("report.published") == 2
        assert kinds.count("review.decided") == 2
        assert kinds.count("review.resume_completed") == 1
        record = await database.get_investigation(
            accepted.investigation_id,
            "phase6-review-owner",
        )
        assert record is not None
        assert record.status == "inconclusive"
    finally:
        if "accepted" in locals():
            await _delete_investigation(database, accepted.investigation_id)
        await database.close()


@pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION") != "1",
    reason="real services not enabled",
)
async def test_cooperative_cancellation_blocks_completion_and_future_claims() -> None:
    settings = Settings()  # type: ignore[call-arg]
    database = Database(settings.app_database_dsn.get_secret_value())
    await database.open()
    try:
        await _migrate(database)
        now = datetime.now(UTC)
        accepted = await database.create_investigation(
            owner_id="phase6-cancel-owner",
            request_id=uuid4(),
            idempotency_key=f"phase6-cancel-{uuid4()}",
            request=InvestigationCreate(
                question="Can a running investigation stop cooperatively?",
                target_service="gateway",
                window_start=now - timedelta(minutes=5),
                window_end=now,
            ),
        )
        lease = await database.claim_job(
            "cancel-worker", lease_seconds=10, investigation_id=accepted.investigation_id
        )
        assert lease is not None
        cancellation = await database.request_cancellation(
            accepted.investigation_id,
            owner_id="phase6-cancel-owner",
        )
        assert cancellation.status == "running"
        with pytest.raises(CancellationRequestedError):
            await database.complete_job(lease)
        assert await database.acknowledge_cancellation(lease) is True
        record = await database.get_investigation(
            accepted.investigation_id,
            "phase6-cancel-owner",
        )
        assert record is not None
        assert record.status == "cancelled"
    finally:
        if "accepted" in locals():
            await _delete_investigation(database, accepted.investigation_id)
        await database.close()


@pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION") != "1",
    reason="real services not enabled",
)
async def test_follow_up_is_versioned_budgeted_idempotent_and_keeps_usage() -> None:
    settings = Settings()  # type: ignore[call-arg]
    database = Database(settings.app_database_dsn.get_secret_value())
    await database.open()
    try:
        await _migrate(database)
        now = datetime.now(UTC)
        accepted = await database.create_investigation(
            owner_id="phase6-followup-owner",
            request_id=uuid4(),
            idempotency_key=f"phase6-followup-{uuid4()}",
            request=InvestigationCreate(
                question="Can a completed report receive a budgeted follow-up?",
                target_service="gateway",
                window_start=now - timedelta(minutes=5),
                window_end=now,
            ),
        )
        lease = await database.claim_job(
            "followup-publisher", lease_seconds=10, investigation_id=accepted.investigation_id
        )
        assert lease is not None
        await database.publish_report_under_lease(
            lease,
            _report(accepted.investigation_id, version=1, now=now, model_calls=3),
            publication_key="followup-base-v1",
            require_review=False,
            review_ttl_seconds=60,
        )
        request = FollowUpCreate(
            question="Does one new bounded metric change the conclusion?",
            max_model_calls=2,
            max_tool_calls=3,
        )
        created = await database.create_follow_up(
            accepted.investigation_id,
            owner_id="phase6-followup-owner",
            idempotency_key="followup-request-1",
            request=request,
        )
        repeated = await database.create_follow_up(
            accepted.investigation_id,
            owner_id="phase6-followup-owner",
            idempotency_key="followup-request-1",
            request=request,
        )
        assert repeated.follow_up_id == created.follow_up_id
        assert created.base_report_version == 1
        assert created.target_report_version == 2

        follow_up_lease = await database.claim_job(
            "followup-worker", lease_seconds=10, investigation_id=accepted.investigation_id
        )
        assert follow_up_lease is not None
        assert follow_up_lease.task_kind == "follow_up"
        context = await database.get_execution_context(follow_up_lease)
        assert context["cumulative_usage"]["model_calls"] == 3
        command = versioned_follow_up(context)
        assert command.update["report_version"] == 2
        assert context["budget"] == {"max_model_calls": 2, "max_tool_calls": 3}
    finally:
        if "accepted" in locals():
            await _delete_investigation(database, accepted.investigation_id)
        await database.close()


@pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION") != "1",
    reason="real services not enabled",
)
async def test_expired_review_is_rejected_without_resuming_work() -> None:
    settings = Settings()  # type: ignore[call-arg]
    database = Database(settings.app_database_dsn.get_secret_value())
    await database.open()
    try:
        await _migrate(database)
        now = datetime.now(UTC)
        accepted = await database.create_investigation(
            owner_id="phase6-expired-review-owner",
            request_id=uuid4(),
            idempotency_key=f"phase6-expired-review-{uuid4()}",
            request=InvestigationCreate(
                question="Must an expired review fail closed without resume?",
                target_service="gateway",
                window_start=now - timedelta(minutes=5),
                window_end=now,
            ),
        )
        lease = await database.claim_job(
            "expiry-publisher", lease_seconds=10, investigation_id=accepted.investigation_id
        )
        assert lease is not None
        await database.publish_report_under_lease(
            lease,
            _report(accepted.investigation_id, version=1, now=now),
            publication_key="expiry-report-v1",
            require_review=True,
            review_ttl_seconds=60,
        )
        async with database.pool.connection() as connection:
            await connection.execute(
                """
                UPDATE incidentgraph_app.review_requests
                SET requested_at = now() - interval '2 minutes',
                    expires_at = now() - interval '1 minute'
                WHERE investigation_id = %s AND report_version = 1
                """,
                (accepted.investigation_id,),
            )
        with pytest.raises(DurableConflictError, match="expired"):
            await database.submit_review(
                accepted.investigation_id,
                reviewer_id="reviewer-expiry",
                roles=frozenset({"reviewer"}),
                idempotency_key="expired-decision-1",
                submission=ReviewSubmission(
                    report_version=1,
                    decision=ReviewDecision.ACCEPT,
                    rationale="This decision arrived after expiration.",
                ),
            )
        assert (
            await database.claim_job(
                "must-not-resume",
                lease_seconds=10,
                investigation_id=accepted.investigation_id,
            )
            is None
        )
    finally:
        if "accepted" in locals():
            await _delete_investigation(database, accepted.investigation_id)
        await database.close()


@pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION") != "1",
    reason="real services not enabled",
)
async def test_coordinator_heartbeats_and_stops_active_work_after_cancellation() -> None:
    class SlowWorkflow:
        def __init__(self) -> None:
            self.cancelled = False

        async def ainvoke(self, value: object, config: dict[str, object]) -> dict[str, object]:
            del value, config
            try:
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                self.cancelled = True
                raise
            return {"status": "unexpected_completion"}

    settings = Settings()  # type: ignore[call-arg]
    database = Database(settings.app_database_dsn.get_secret_value())
    await database.open()
    try:
        await _migrate(database)
        now = datetime.now(UTC)
        accepted = await database.create_investigation(
            owner_id="phase6-active-cancel-owner",
            request_id=uuid4(),
            idempotency_key=f"phase6-active-cancel-{uuid4()}",
            request=InvestigationCreate(
                question="Will an active coordinator stop at cancellation?",
                target_service="gateway",
                window_start=now - timedelta(minutes=5),
                window_end=now,
            ),
        )
        lease = await database.claim_job(
            "active-cancel-worker",
            lease_seconds=3,
            investigation_id=accepted.investigation_id,
        )
        assert lease is not None
        workflow = SlowWorkflow()
        coordinator = DurableWorkflowCoordinator(
            database,
            workflow,
            require_review=False,
            review_ttl_seconds=60,
            lease_seconds=3,
        )
        processing = asyncio.create_task(
            coordinator.process(
                lease,
                initial_input={"investigation_id": str(accepted.investigation_id)},
            )
        )
        await asyncio.sleep(0.1)
        await database.request_cancellation(
            accepted.investigation_id,
            owner_id="phase6-active-cancel-owner",
        )
        result = await processing
        assert result["status"] == "cancelled"
        assert workflow.cancelled is True
    finally:
        if "accepted" in locals():
            await _delete_investigation(database, accepted.investigation_id)
        await database.close()
