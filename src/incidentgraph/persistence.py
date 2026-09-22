from __future__ import annotations

import asyncio
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
    EventRecord,
    InvestigationAccepted,
    InvestigationCreate,
    InvestigationRecord,
    JobLease,
)


class LeaseLostError(RuntimeError):
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

    async def claim_job(self, worker_id: str, lease_seconds: int) -> JobLease | None:
        lease_token = uuid4()
        async with self.pool.connection() as connection:
            async with connection.transaction():
                cursor = await connection.execute(
                    """
                    WITH candidate AS (
                        SELECT id
                        FROM incidentgraph_app.jobs
                        WHERE attempt < max_attempts
                          AND available_at <= now()
                          AND (
                              status = 'queued'
                              OR (status = 'running' AND leased_until <= now())
                          )
                        ORDER BY id
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
                              job.lease_token, job.attempt, job.leased_until
                    """,
                    (worker_id, lease_token, lease_seconds),
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
                )
                return JobLease.model_validate(row)

    async def complete_job(self, lease: JobLease) -> None:
        async with self.pool.connection() as connection:
            async with connection.transaction():
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

    async def _append_event(
        self,
        connection: AsyncConnection[dict[str, Any]],
        investigation_id: UUID,
        kind: str,
        payload: dict[str, Any],
    ) -> None:
        await connection.execute(
            """
            INSERT INTO incidentgraph_app.events (investigation_id, sequence, kind, payload)
            SELECT %s, COALESCE(MAX(sequence), 0) + 1, %s, %s
            FROM incidentgraph_app.events
            WHERE investigation_id = %s
            """,
            (investigation_id, kind, Jsonb(payload), investigation_id),
        )
