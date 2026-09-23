from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

from psycopg import AsyncConnection
from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from incidentgraph.models import (
    CancellationRecord,
    EventRecord,
    EvidenceItem,
    FollowUpCreate,
    FollowUpRecord,
    InvestigationAccepted,
    InvestigationCreate,
    InvestigationRecord,
    InvestigationReport,
    InvestigationStatus,
    JobLease,
    PublicationResult,
    ReviewDecision,
    ReviewRecord,
    ReviewStatus,
    ReviewSubmission,
)


class LeaseLostError(RuntimeError):
    pass


class DurableConflictError(RuntimeError):
    pass


class ReviewAuthorizationError(PermissionError):
    pass


class CancellationRequestedError(RuntimeError):
    pass


class Database:
    def __init__(self, dsn: str) -> None:
        self.pool = cast(
            AsyncConnectionPool[AsyncConnection[dict[str, Any]]],
            AsyncConnectionPool(
                conninfo=dsn,
                min_size=1,
                max_size=4,
                open=False,
                kwargs={"row_factory": dict_row},
            ),
        )

    async def open(self) -> None:
        await self.pool.open(wait=True, timeout=10)

    async def close(self) -> None:
        await self.pool.close()

    async def ping(self) -> bool:
        async with self.pool.connection() as connection:
            result = await connection.execute("SELECT 1 AS ok")
            row = await result.fetchone()
            return bool(row and row["ok"] == 1)

    async def apply_migration(self, path: Path) -> None:
        statement = await asyncio.to_thread(path.read_text, encoding="utf-8")
        async with self.pool.connection() as connection:
            async with connection.transaction():
                await connection.execute(statement)

    async def persist_evidence(
        self, investigation_id: UUID, items: Sequence[EvidenceItem]
    ) -> None:
        """Persist full immutable evidence before only references enter checkpoint state."""
        async with self.pool.connection() as connection:
            async with connection.transaction():
                for item in items:
                    cursor = await connection.execute(
                        """
                        INSERT INTO incidentgraph_app.evidence (
                            investigation_id, evidence_id, content_hash, payload
                        ) VALUES (%s, %s, %s, %s)
                        ON CONFLICT (investigation_id, evidence_id) DO NOTHING
                        RETURNING content_hash
                        """,
                        (
                            investigation_id,
                            item.evidence_id,
                            item.content_hash,
                            Jsonb(item.model_dump(mode="json")),
                        ),
                    )
                    inserted = await cursor.fetchone()
                    if inserted is None:
                        existing_cursor = await connection.execute(
                            """
                            SELECT content_hash
                            FROM incidentgraph_app.evidence
                            WHERE investigation_id = %s AND evidence_id = %s
                            """,
                            (investigation_id, item.evidence_id),
                        )
                        existing = await existing_cursor.fetchone()
                        if existing is None or existing["content_hash"] != item.content_hash:
                            raise ValueError("immutable evidence ID collision")

    async def persist_report(self, report: InvestigationReport) -> None:
        payload = report.model_dump(mode="json")
        async with self.pool.connection() as connection:
            async with connection.transaction():
                cursor = await connection.execute(
                    """
                    INSERT INTO incidentgraph_app.reports (
                        investigation_id, report_version, outcome, payload
                    ) VALUES (%s, %s, %s, %s)
                    ON CONFLICT (investigation_id, report_version) DO NOTHING
                    RETURNING payload
                    """,
                    (
                        report.investigation_id,
                        report.report_version,
                        report.outcome.value,
                        Jsonb(payload),
                    ),
                )
                inserted = await cursor.fetchone()
                if inserted is None:
                    existing_cursor = await connection.execute(
                        """
                        SELECT payload
                        FROM incidentgraph_app.reports
                        WHERE investigation_id = %s AND report_version = %s
                        """,
                        (report.investigation_id, report.report_version),
                    )
                    existing = await existing_cursor.fetchone()
                    if existing is None or existing["payload"] != payload:
                        raise ValueError("immutable report version collision")

    async def get_evidence(
        self, investigation_id: UUID, evidence_id: UUID
    ) -> EvidenceItem | None:
        async with self.pool.connection() as connection:
            cursor = await connection.execute(
                """
                SELECT payload
                FROM incidentgraph_app.evidence
                WHERE investigation_id = %s AND evidence_id = %s
                """,
                (investigation_id, evidence_id),
            )
            row = await cursor.fetchone()
            return EvidenceItem.model_validate(row["payload"]) if row else None

    async def get_report(
        self, investigation_id: UUID, report_version: int
    ) -> InvestigationReport | None:
        async with self.pool.connection() as connection:
            cursor = await connection.execute(
                """
                SELECT payload
                FROM incidentgraph_app.reports
                WHERE investigation_id = %s AND report_version = %s
                """,
                (investigation_id, report_version),
            )
            row = await cursor.fetchone()
            return InvestigationReport.model_validate(row["payload"]) if row else None

    async def create_investigation(
        self,
        *,
        owner_id: str,
        request_id: UUID,
        idempotency_key: str,
        request: InvestigationCreate,
    ) -> InvestigationAccepted:
        investigation_id = uuid4()
        async with self.pool.connection() as connection:
            try:
                async with connection.transaction():
                    cursor = await connection.execute(
                        """
                        INSERT INTO incidentgraph_app.investigations (
                            id, owner_id, request_id, idempotency_key, question,
                            target_service, environment, window_start, window_end, mode, status
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'queued')
                        RETURNING id AS investigation_id, status, created_at
                        """,
                        (
                            investigation_id,
                            owner_id,
                            request_id,
                            idempotency_key,
                            request.question,
                            request.target_service,
                            request.environment,
                            request.window_start,
                            request.window_end,
                            request.mode.value,
                        ),
                    )
                    row = await cursor.fetchone()
                    await connection.execute(
                        """
                        INSERT INTO incidentgraph_app.jobs (investigation_id, status)
                        VALUES (%s, 'queued')
                        """,
                        (investigation_id,),
                    )
                    await self._append_event(
                        connection,
                        investigation_id,
                        "investigation.queued",
                        {"request_id": str(request_id)},
                    )
            except UniqueViolation:
                async with self.pool.connection() as lookup:
                    cursor = await lookup.execute(
                        """
                        SELECT id AS investigation_id, status, created_at
                        FROM incidentgraph_app.investigations
                        WHERE owner_id = %s AND idempotency_key = %s
                        """,
                        (owner_id, idempotency_key),
                    )
                    row = await cursor.fetchone()
            if row is None:
                raise RuntimeError("investigation creation did not return a record")
            return InvestigationAccepted.model_validate(row)

    async def get_investigation(
        self,
        investigation_id: UUID,
        owner_id: str,
    ) -> InvestigationRecord | None:
        async with self.pool.connection() as connection:
            cursor = await connection.execute(
                """
                SELECT id AS investigation_id, owner_id, request_id, question, target_service,
                       environment, window_start, window_end, mode, status, created_at, updated_at
                FROM incidentgraph_app.investigations
                WHERE id = %s AND owner_id = %s
                """,
                (investigation_id, owner_id),
            )
            row = await cursor.fetchone()
            return InvestigationRecord.model_validate(row) if row else None

    async def list_events(self, investigation_id: UUID, owner_id: str) -> Sequence[EventRecord]:
        async with self.pool.connection() as connection:
            cursor = await connection.execute(
                """
                SELECT e.investigation_id, e.sequence, e.kind, e.payload, e.created_at
                FROM incidentgraph_app.events e
                JOIN incidentgraph_app.investigations i ON i.id = e.investigation_id
                WHERE e.investigation_id = %s AND i.owner_id = %s
                ORDER BY e.sequence
                """,
                (investigation_id, owner_id),
            )
            return [EventRecord.model_validate(row) for row in await cursor.fetchall()]

    async def claim_job(
        self,
        worker_id: str,
        lease_seconds: int,
        investigation_id: UUID | None = None,
    ) -> JobLease | None:
        lease_token = uuid4()
        async with self.pool.connection() as connection:
            async with connection.transaction():
                cursor = await connection.execute(
                    """
                    WITH candidate AS (
                        SELECT job.id
                        FROM incidentgraph_app.jobs job
                        JOIN incidentgraph_app.investigations investigation
                          ON investigation.id = job.investigation_id
                        WHERE job.attempt < job.max_attempts
                          AND job.available_at <= now()
                          AND investigation.cancellation_requested_at IS NULL
                          AND (%s::uuid IS NULL OR job.investigation_id = %s::uuid)
                          AND (
                              job.status = 'queued'
                              OR (job.status = 'running' AND job.leased_until <= now())
                          )
                        ORDER BY job.id
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1
                    )
                    UPDATE incidentgraph_app.jobs AS job
                    SET status = 'running',
                        attempt = job.attempt + 1,
                        lease_owner = %s,
                        lease_token = %s,
                        leased_until = now() + (%s * interval '1 second'),
                        heartbeat_at = now(),
                        updated_at = now()
                    FROM candidate
                    WHERE job.id = candidate.id
                    RETURNING job.id AS job_id, job.investigation_id, job.lease_owner,
                              job.lease_token, job.attempt, job.leased_until,
                              job.generation, job.task_kind, job.target_report_version
                    """,
                    (
                        investigation_id,
                        investigation_id,
                        worker_id,
                        lease_token,
                        lease_seconds,
                    ),
                )
                row = await cursor.fetchone()
                if row is None:
                    return None
                await connection.execute(
                    """
                    UPDATE incidentgraph_app.investigations
                    SET status = 'running', updated_at = now()
                    WHERE id = %s
                    """,
                    (row["investigation_id"],),
                )
                await self._append_event(
                    connection,
                    row["investigation_id"],
                    "job.started",
                    {"attempt": row["attempt"], "worker_id": worker_id},
                    deduplication_key=(
                        f"job.started:{row['generation']}:{row['attempt']}"
                    ),
                )
                return JobLease.model_validate(row)

    async def complete_job(self, lease: JobLease) -> None:
        async with self.pool.connection() as connection:
            async with connection.transaction():
                job = await self._lock_valid_lease(connection, lease)
                if job["cancellation_requested_at"] is not None:
                    raise CancellationRequestedError("investigation cancellation was requested")
                cursor = await connection.execute(
                    """
                    UPDATE incidentgraph_app.jobs
                    SET status = 'completed', leased_until = NULL,
                        heartbeat_at = now(), updated_at = now()
                    WHERE id = %s AND lease_owner = %s AND lease_token = %s
                      AND status = 'running' AND leased_until > now()
                    """,
                    (lease.job_id, lease.lease_owner, lease.lease_token),
                )
                if cursor.rowcount != 1:
                    raise LeaseLostError("worker no longer owns the job lease")
                await connection.execute(
                    """
                    UPDATE incidentgraph_app.investigations
                    SET status = 'completed', updated_at = now()
                    WHERE id = %s
                    """,
                    (lease.investigation_id,),
                )
                await self._append_event(
                    connection,
                    lease.investigation_id,
                    "job.completed",
                    {"attempt": lease.attempt, "worker_id": lease.lease_owner},
                    deduplication_key=f"job.completed:{lease.generation}",
                )

    async def heartbeat(self, lease: JobLease, lease_seconds: int) -> None:
        async with self.pool.connection() as connection:
            cursor = await connection.execute(
                """
                UPDATE incidentgraph_app.jobs
                SET leased_until = now() + (%s * interval '1 second'),
                    heartbeat_at = now(), updated_at = now()
                WHERE id = %s AND lease_owner = %s AND lease_token = %s
                  AND status = 'running' AND leased_until > now()
                """,
                (lease_seconds, lease.job_id, lease.lease_owner, lease.lease_token),
            )
            if cursor.rowcount != 1:
                raise LeaseLostError("worker no longer owns the job lease")

    async def publish_report_under_lease(
        self,
        lease: JobLease,
        report: InvestigationReport,
        *,
        publication_key: str,
        require_review: bool,
        review_ttl_seconds: int,
        evidence_summary: Sequence[dict[str, Any]] = (),
        uncertainties: Sequence[str] = (),
    ) -> PublicationResult:
        """Atomically publish once, fence stale attempts, and release review waits."""
        if report.investigation_id != lease.investigation_id:
            raise ValueError("report and lease investigation IDs differ")
        if report.report_version != lease.target_report_version:
            raise ValueError("report version does not match the leased work item")
        payload = report.model_dump(mode="json")
        report_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        async with self.pool.connection() as connection:
            async with connection.transaction():
                existing_cursor = await connection.execute(
                    """
                    SELECT publication.report_version, publication.report_hash,
                           publication.lease_token, investigation.status,
                           review.id AS review_id
                    FROM incidentgraph_app.report_publications publication
                    JOIN incidentgraph_app.investigations investigation
                      ON investigation.id = publication.investigation_id
                    LEFT JOIN incidentgraph_app.review_requests review
                      ON review.investigation_id = publication.investigation_id
                     AND review.report_version = publication.report_version
                    WHERE publication.investigation_id = %s
                      AND publication.publication_key = %s
                    """,
                    (lease.investigation_id, publication_key),
                )
                existing = await existing_cursor.fetchone()
                if existing is not None:
                    if (
                        existing["lease_token"] != lease.lease_token
                        or existing["report_hash"] != report_hash
                        or existing["report_version"] != report.report_version
                    ):
                        raise LeaseLostError("publication key belongs to another worker outcome")
                    return PublicationResult(
                        investigation_id=lease.investigation_id,
                        report_version=report.report_version,
                        status=InvestigationStatus(existing["status"]),
                        duplicate=True,
                        review_id=existing["review_id"],
                    )

                job = await self._lock_valid_lease(connection, lease)
                if job["cancellation_requested_at"] is not None:
                    raise CancellationRequestedError("investigation cancellation was requested")

                inserted = await connection.execute(
                    """
                    INSERT INTO incidentgraph_app.reports (
                        investigation_id, report_version, outcome, payload
                    ) VALUES (%s, %s, %s, %s)
                    ON CONFLICT (investigation_id, report_version) DO NOTHING
                    RETURNING payload
                    """,
                    (
                        report.investigation_id,
                        report.report_version,
                        report.outcome.value,
                        Jsonb(payload),
                    ),
                )
                if await inserted.fetchone() is None:
                    report_cursor = await connection.execute(
                        """
                        SELECT payload FROM incidentgraph_app.reports
                        WHERE investigation_id = %s AND report_version = %s
                        """,
                        (report.investigation_id, report.report_version),
                    )
                    stored = await report_cursor.fetchone()
                    if stored is None or stored["payload"] != payload:
                        raise DurableConflictError("immutable report version collision")

                await connection.execute(
                    """
                    INSERT INTO incidentgraph_app.report_publications (
                        investigation_id, report_version, publication_key, report_hash,
                        outcome, published_by_attempt, lease_token
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        report.investigation_id,
                        report.report_version,
                        publication_key,
                        report_hash,
                        report.outcome.value,
                        lease.attempt,
                        lease.lease_token,
                    ),
                )
                await connection.execute(
                    """
                    UPDATE incidentgraph_app.investigations
                    SET current_report_version = %s,
                        cumulative_usage = %s,
                        updated_at = now()
                    WHERE id = %s
                    """,
                    (
                        report.report_version,
                        Jsonb(report.usage_and_timing.model_dump(mode="json")),
                        lease.investigation_id,
                    ),
                )
                await self._append_event(
                    connection,
                    lease.investigation_id,
                    "report.published",
                    {"report_version": report.report_version, "outcome": report.outcome.value},
                    deduplication_key=f"report.published:{report.report_version}",
                )

                review_id: UUID | None = None
                if require_review:
                    review_id = uuid4()
                    review_cursor = await connection.execute(
                        """
                        INSERT INTO incidentgraph_app.review_requests (
                            id, investigation_id, report_version, evidence_summary,
                            uncertainties, allowed_decisions, expires_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s,
                            now() + (%s * interval '1 second')
                        )
                        ON CONFLICT (investigation_id, report_version) DO NOTHING
                        RETURNING id
                        """,
                        (
                            review_id,
                            lease.investigation_id,
                            report.report_version,
                            Jsonb(list(evidence_summary)),
                            Jsonb(list(uncertainties)),
                            Jsonb(["accept", "reject", "request_revision"]),
                            review_ttl_seconds,
                        ),
                    )
                    review_row = await review_cursor.fetchone()
                    if review_row is None:
                        raise DurableConflictError("review request already exists")
                    await connection.execute(
                        """
                        UPDATE incidentgraph_app.jobs
                        SET status = 'waiting', lease_owner = NULL, lease_token = NULL,
                            leased_until = NULL, heartbeat_at = NULL, updated_at = now()
                        WHERE id = %s
                        """,
                        (lease.job_id,),
                    )
                    await connection.execute(
                        """
                        UPDATE incidentgraph_app.investigations
                        SET status = 'waiting_for_review', updated_at = now()
                        WHERE id = %s
                        """,
                        (lease.investigation_id,),
                    )
                    await self._append_event(
                        connection,
                        lease.investigation_id,
                        "review.requested",
                        {"review_id": str(review_id), "report_version": report.report_version},
                        deduplication_key=f"review.requested:{report.report_version}",
                    )
                    result_status = InvestigationStatus.WAITING_FOR_REVIEW
                else:
                    result_status = (
                        InvestigationStatus.INCONCLUSIVE
                        if report.outcome.value == "inconclusive"
                        else InvestigationStatus.COMPLETED
                    )
                    await connection.execute(
                        """
                        UPDATE incidentgraph_app.jobs
                        SET status = 'completed', lease_owner = NULL, lease_token = NULL,
                            leased_until = NULL, heartbeat_at = now(), updated_at = now()
                        WHERE id = %s
                        """,
                        (lease.job_id,),
                    )
                    await connection.execute(
                        """
                        UPDATE incidentgraph_app.investigations
                        SET status = %s, updated_at = now() WHERE id = %s
                        """,
                        (result_status.value, lease.investigation_id),
                    )
                    await self._append_event(
                        connection,
                        lease.investigation_id,
                        "investigation.finalized",
                        {"report_version": report.report_version},
                        deduplication_key=f"investigation.finalized:{report.report_version}",
                    )
                return PublicationResult(
                    investigation_id=lease.investigation_id,
                    report_version=report.report_version,
                    status=result_status,
                    duplicate=False,
                    review_id=review_id,
                )

    async def submit_review(
        self,
        investigation_id: UUID,
        *,
        reviewer_id: str,
        roles: frozenset[str],
        idempotency_key: str,
        submission: ReviewSubmission,
    ) -> ReviewRecord:
        if not roles.intersection({"reviewer", "operator"}):
            raise ReviewAuthorizationError("reviewer or operator role required")
        async with self.pool.connection() as connection:
            async with connection.transaction():
                prior_cursor = await connection.execute(
                    """
                    SELECT request.id AS review_id, request.investigation_id,
                           request.report_version, request.status, request.reviewer_id,
                           request.requested_at, request.expires_at, request.decided_at
                    FROM incidentgraph_app.review_decisions decision
                    JOIN incidentgraph_app.review_requests request
                      ON request.id = decision.review_request_id
                    WHERE decision.reviewer_id = %s AND decision.idempotency_key = %s
                    """,
                    (reviewer_id, idempotency_key),
                )
                prior = await prior_cursor.fetchone()
                if prior is not None:
                    return ReviewRecord.model_validate(prior)

                review_cursor = await connection.execute(
                    """
                    SELECT request.id AS review_id, request.investigation_id,
                           request.report_version, request.status, request.reviewer_id,
                           request.requested_at, request.expires_at, request.decided_at
                    FROM incidentgraph_app.review_requests request
                    WHERE request.investigation_id = %s AND request.report_version = %s
                    FOR UPDATE
                    """,
                    (investigation_id, submission.report_version),
                )
                review = await review_cursor.fetchone()
                if review is None:
                    raise DurableConflictError("stale or mismatched report version")
                if review["status"] != "pending":
                    raise DurableConflictError("review request is no longer pending")
                expired_cursor = await connection.execute(
                    "SELECT %s <= now() AS expired",
                    (review["expires_at"],),
                )
                expired = await expired_cursor.fetchone()
                if expired and expired["expired"]:
                    await connection.execute(
                        """
                        UPDATE incidentgraph_app.review_requests
                        SET status = 'expired' WHERE id = %s
                        """,
                        (review["review_id"],),
                    )
                    raise DurableConflictError("review request expired")

                status_value = {
                    ReviewDecision.ACCEPT: ReviewStatus.ACCEPTED,
                    ReviewDecision.REJECT: ReviewStatus.REJECTED,
                    ReviewDecision.REQUEST_REVISION: ReviewStatus.REVISION_REQUESTED,
                }[submission.decision]
                await connection.execute(
                    """
                    UPDATE incidentgraph_app.review_requests
                    SET status = %s, reviewer_id = %s, decided_at = now()
                    WHERE id = %s
                    """,
                    (status_value.value, reviewer_id, review["review_id"]),
                )
                await connection.execute(
                    """
                    INSERT INTO incidentgraph_app.review_decisions (
                        id, review_request_id, investigation_id, report_version,
                        reviewer_id, idempotency_key, decision, rationale
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        uuid4(),
                        review["review_id"],
                        investigation_id,
                        submission.report_version,
                        reviewer_id,
                        idempotency_key,
                        submission.decision.value,
                        submission.rationale,
                    ),
                )

                is_revision = submission.decision == ReviewDecision.REQUEST_REVISION
                await connection.execute(
                    """
                    UPDATE incidentgraph_app.jobs
                    SET status = 'queued', attempt = 0, generation = generation + 1,
                        task_kind = %s, target_report_version = %s,
                        input_payload = %s, available_at = now(),
                        lease_owner = NULL, lease_token = NULL, leased_until = NULL,
                        heartbeat_at = NULL, updated_at = now()
                    WHERE investigation_id = %s AND status = 'waiting'
                    """,
                    (
                        "review_revision" if is_revision else "review_resume",
                        submission.report_version + 1 if is_revision else submission.report_version,
                        Jsonb(
                            {
                                "review_id": str(review["review_id"]),
                                "decision": submission.decision.value,
                                "rationale": submission.rationale,
                            }
                        ),
                        investigation_id,
                    ),
                )
                await connection.execute(
                    """
                    UPDATE incidentgraph_app.investigations
                    SET status = 'queued', updated_at = now() WHERE id = %s
                    """,
                    (investigation_id,),
                )
                await self._append_event(
                    connection,
                    investigation_id,
                    "review.decided",
                    {
                        "review_id": str(review["review_id"]),
                        "report_version": submission.report_version,
                        "decision": submission.decision.value,
                        "reviewer_id": reviewer_id,
                    },
                    deduplication_key=f"review.decision:{reviewer_id}:{idempotency_key}",
                )
                result_cursor = await connection.execute(
                    """
                    SELECT id AS review_id, investigation_id, report_version, status,
                           reviewer_id, requested_at, expires_at, decided_at
                    FROM incidentgraph_app.review_requests WHERE id = %s
                    """,
                    (review["review_id"],),
                )
                result = await result_cursor.fetchone()
                if result is None:
                    raise RuntimeError("review decision disappeared")
                return ReviewRecord.model_validate(result)

    async def complete_review_resume(self, lease: JobLease) -> InvestigationStatus:
        """Finalize an accepted/rejected review from a controlled worker attempt."""
        if lease.task_kind != "review_resume":
            raise ValueError("lease is not a terminal review resume")
        async with self.pool.connection() as connection:
            async with connection.transaction():
                job = await self._lock_valid_lease(connection, lease)
                if job["cancellation_requested_at"] is not None:
                    raise CancellationRequestedError("investigation cancellation was requested")
                payload_cursor = await connection.execute(
                    """
                    SELECT input_payload FROM incidentgraph_app.jobs WHERE id = %s
                    """,
                    (lease.job_id,),
                )
                payload_row = await payload_cursor.fetchone()
                if payload_row is None:
                    raise LeaseLostError("review resume work item disappeared")
                payload = payload_row["input_payload"]
                decision = payload.get("decision") if isinstance(payload, dict) else None
                if decision not in {"accept", "reject"}:
                    raise DurableConflictError("stored review decision is not terminal")
                terminal_status = InvestigationStatus.FAILED
                job_status = "failed"
                if decision == "accept":
                    outcome_cursor = await connection.execute(
                        """
                        SELECT outcome FROM incidentgraph_app.report_publications
                        WHERE investigation_id = %s AND report_version = %s
                        """,
                        (lease.investigation_id, lease.target_report_version),
                    )
                    outcome = await outcome_cursor.fetchone()
                    if outcome is None:
                        raise DurableConflictError("accepted review has no published report")
                    terminal_status = (
                        InvestigationStatus.INCONCLUSIVE
                        if outcome["outcome"] == "inconclusive"
                        else InvestigationStatus.COMPLETED
                    )
                    job_status = "completed"
                await connection.execute(
                    """
                    UPDATE incidentgraph_app.jobs
                    SET status = %s, lease_owner = NULL, lease_token = NULL,
                        leased_until = NULL, heartbeat_at = now(), updated_at = now()
                    WHERE id = %s
                    """,
                    (job_status, lease.job_id),
                )
                await connection.execute(
                    """
                    UPDATE incidentgraph_app.investigations
                    SET status = %s, updated_at = now() WHERE id = %s
                    """,
                    (terminal_status.value, lease.investigation_id),
                )
                await self._append_event(
                    connection,
                    lease.investigation_id,
                    "review.resume_completed",
                    {
                        "decision": decision,
                        "report_version": lease.target_report_version,
                        "attempt": lease.attempt,
                    },
                    deduplication_key=f"review.resume:{lease.generation}",
                )
                return terminal_status

    async def request_cancellation(
        self, investigation_id: UUID, *, owner_id: str
    ) -> CancellationRecord:
        async with self.pool.connection() as connection:
            async with connection.transaction():
                cursor = await connection.execute(
                    """
                    SELECT id, status, cancellation_requested_at
                    FROM incidentgraph_app.investigations
                    WHERE id = %s AND owner_id = %s
                    FOR UPDATE
                    """,
                    (investigation_id, owner_id),
                )
                investigation = await cursor.fetchone()
                if investigation is None:
                    raise DurableConflictError("investigation not found")
                requested_at = investigation["cancellation_requested_at"]
                if requested_at is not None:
                    return CancellationRecord(
                        investigation_id=investigation_id,
                        status=InvestigationStatus(investigation["status"]),
                        cancellation_requested_at=requested_at,
                    )
                if investigation["status"] in {"completed", "inconclusive", "failed"}:
                    raise DurableConflictError("terminal investigation cannot be cancelled")
                timestamp_cursor = await connection.execute("SELECT now() AS requested_at")
                timestamp = await timestamp_cursor.fetchone()
                if timestamp is None:
                    raise RuntimeError("database clock unavailable")
                requested_at = timestamp["requested_at"]
                immediate = investigation["status"] in {"queued", "waiting_for_review"}
                new_status = "cancelled" if immediate else investigation["status"]
                await connection.execute(
                    """
                    UPDATE incidentgraph_app.investigations
                    SET cancellation_requested_at = %s, status = %s, updated_at = now()
                    WHERE id = %s
                    """,
                    (requested_at, new_status, investigation_id),
                )
                if immediate:
                    await connection.execute(
                        """
                        UPDATE incidentgraph_app.jobs
                        SET status = 'cancelled', lease_owner = NULL, lease_token = NULL,
                            leased_until = NULL, heartbeat_at = NULL, updated_at = now()
                        WHERE investigation_id = %s
                        """,
                        (investigation_id,),
                    )
                await self._append_event(
                    connection,
                    investigation_id,
                    "investigation.cancellation_requested",
                    {"immediate": immediate},
                    deduplication_key="investigation.cancellation_requested",
                )
                return CancellationRecord(
                    investigation_id=investigation_id,
                    status=InvestigationStatus(new_status),
                    cancellation_requested_at=requested_at,
                )

    async def acknowledge_cancellation(self, lease: JobLease) -> bool:
        async with self.pool.connection() as connection:
            async with connection.transaction():
                job = await self._lock_valid_lease(connection, lease)
                if job["cancellation_requested_at"] is None:
                    return False
                await connection.execute(
                    """
                    UPDATE incidentgraph_app.jobs
                    SET status = 'cancelled', lease_owner = NULL, lease_token = NULL,
                        leased_until = NULL, heartbeat_at = NULL, updated_at = now()
                    WHERE id = %s
                    """,
                    (lease.job_id,),
                )
                await connection.execute(
                    """
                    UPDATE incidentgraph_app.investigations
                    SET status = 'cancelled', updated_at = now() WHERE id = %s
                    """,
                    (lease.investigation_id,),
                )
                await self._append_event(
                    connection,
                    lease.investigation_id,
                    "investigation.cancelled",
                    {"attempt": lease.attempt},
                    deduplication_key="investigation.cancelled",
                )
                return True

    async def cancellation_requested(self, lease: JobLease) -> bool:
        async with self.pool.connection() as connection:
            async with connection.transaction():
                job = await self._lock_valid_lease(connection, lease)
                return job["cancellation_requested_at"] is not None

    async def create_follow_up(
        self,
        investigation_id: UUID,
        *,
        owner_id: str,
        idempotency_key: str,
        request: FollowUpCreate,
    ) -> FollowUpRecord:
        async with self.pool.connection() as connection:
            async with connection.transaction():
                prior_cursor = await connection.execute(
                    """
                    SELECT id AS follow_up_id, investigation_id, base_report_version,
                           target_report_version, created_at
                    FROM incidentgraph_app.follow_ups
                    WHERE owner_id = %s AND idempotency_key = %s
                    """,
                    (owner_id, idempotency_key),
                )
                prior = await prior_cursor.fetchone()
                if prior is not None:
                    return FollowUpRecord(**prior, status=InvestigationStatus.QUEUED)
                cursor = await connection.execute(
                    """
                    SELECT id, status, current_report_version
                    FROM incidentgraph_app.investigations
                    WHERE id = %s AND owner_id = %s
                    FOR UPDATE
                    """,
                    (investigation_id, owner_id),
                )
                investigation = await cursor.fetchone()
                if investigation is None:
                    raise DurableConflictError("investigation not found")
                if investigation["status"] not in {"completed", "inconclusive"}:
                    raise DurableConflictError("follow-up requires a completed accepted report")
                base_version = int(investigation["current_report_version"])
                if base_version < 1:
                    raise DurableConflictError("follow-up requires a published base report")
                target_version = base_version + 1
                follow_up_id = uuid4()
                budget = {
                    "max_model_calls": request.max_model_calls,
                    "max_tool_calls": request.max_tool_calls,
                }
                created_cursor = await connection.execute(
                    """
                    INSERT INTO incidentgraph_app.follow_ups (
                        id, investigation_id, owner_id, idempotency_key,
                        base_report_version, target_report_version, question, budget
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING created_at
                    """,
                    (
                        follow_up_id,
                        investigation_id,
                        owner_id,
                        idempotency_key,
                        base_version,
                        target_version,
                        request.question,
                        Jsonb(budget),
                    ),
                )
                created = await created_cursor.fetchone()
                if created is None:
                    raise RuntimeError("follow-up creation did not return a timestamp")
                await connection.execute(
                    """
                    UPDATE incidentgraph_app.jobs
                    SET status = 'queued', attempt = 0, generation = generation + 1,
                        task_kind = 'follow_up', target_report_version = %s,
                        input_payload = %s, budget = %s, available_at = now(),
                        lease_owner = NULL, lease_token = NULL, leased_until = NULL,
                        heartbeat_at = NULL, updated_at = now()
                    WHERE investigation_id = %s
                    """,
                    (
                        target_version,
                        Jsonb({"follow_up_id": str(follow_up_id), "question": request.question}),
                        Jsonb(budget),
                        investigation_id,
                    ),
                )
                await connection.execute(
                    """
                    UPDATE incidentgraph_app.investigations
                    SET status = 'queued', updated_at = now() WHERE id = %s
                    """,
                    (investigation_id,),
                )
                await self._append_event(
                    connection,
                    investigation_id,
                    "follow_up.queued",
                    {
                        "follow_up_id": str(follow_up_id),
                        "base_report_version": base_version,
                        "target_report_version": target_version,
                        "budget": budget,
                    },
                    deduplication_key=f"follow_up:{follow_up_id}",
                )
                return FollowUpRecord(
                    follow_up_id=follow_up_id,
                    investigation_id=investigation_id,
                    base_report_version=base_version,
                    target_report_version=target_version,
                    status=InvestigationStatus.QUEUED,
                    created_at=created["created_at"],
                )

    async def get_execution_context(self, lease: JobLease) -> dict[str, Any]:
        """Return only server-stored resume input after rechecking the active lease."""
        async with self.pool.connection() as connection:
            async with connection.transaction():
                await self._lock_valid_lease(connection, lease)
                cursor = await connection.execute(
                    """
                    SELECT investigation.thread_id, investigation.cumulative_usage,
                           job.task_kind, job.target_report_version,
                           job.input_payload, job.budget
                    FROM incidentgraph_app.jobs job
                    JOIN incidentgraph_app.investigations investigation
                      ON investigation.id = job.investigation_id
                    WHERE job.id = %s
                    """,
                    (lease.job_id,),
                )
                row = await cursor.fetchone()
                if row is None:
                    raise LeaseLostError("leased work item disappeared")
                return dict(row)

    async def _lock_valid_lease(
        self,
        connection: AsyncConnection[dict[str, Any]],
        lease: JobLease,
    ) -> dict[str, Any]:
        cursor = await connection.execute(
            """
            SELECT job.id, investigation.cancellation_requested_at
            FROM incidentgraph_app.jobs job
            JOIN incidentgraph_app.investigations investigation
              ON investigation.id = job.investigation_id
            WHERE job.id = %s AND job.investigation_id = %s
              AND job.lease_owner = %s AND job.lease_token = %s
              AND job.status = 'running' AND job.leased_until > now()
            FOR UPDATE OF job, investigation
            """,
            (
                lease.job_id,
                lease.investigation_id,
                lease.lease_owner,
                lease.lease_token,
            ),
        )
        row = await cursor.fetchone()
        if row is None:
            raise LeaseLostError("worker no longer owns the job lease")
        return row

    async def _append_event(
        self,
        connection: AsyncConnection[dict[str, Any]],
        investigation_id: UUID,
        kind: str,
        payload: dict[str, Any],
        deduplication_key: str | None = None,
    ) -> None:
        await connection.execute(
            "SELECT id FROM incidentgraph_app.investigations WHERE id = %s FOR UPDATE",
            (investigation_id,),
        )
        await connection.execute(
            """
            INSERT INTO incidentgraph_app.events (
                investigation_id, sequence, kind, payload, deduplication_key
            )
            SELECT %s, COALESCE(MAX(sequence), 0) + 1, %s, %s, %s
            FROM incidentgraph_app.events
            WHERE investigation_id = %s
            ON CONFLICT (investigation_id, deduplication_key)
                WHERE deduplication_key IS NOT NULL DO NOTHING
            """,
            (
                investigation_id,
                kind,
                Jsonb(payload),
                deduplication_key,
                investigation_id,
            ),
        )
