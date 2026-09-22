from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class InvestigationStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_FOR_REVIEW = "waiting_for_review"
    COMPLETED = "completed"
    INCONCLUSIVE = "inconclusive"
    FAILED = "failed"
    CANCELLED = "cancelled"


class InvestigationMode(StrEnum):
    LIVE = "live"
    REPLAY = "replay"


ServiceId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{0,62}$")]


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a UTC offset")
    return value.astimezone(UTC)


class InvestigationCreate(BaseModel):
    question: str = Field(min_length=8, max_length=2_000)
    target_service: ServiceId
    environment: Literal["lab"] = "lab"
    window_start: datetime
    window_end: datetime
    mode: InvestigationMode = InvestigationMode.REPLAY

    _normalize_start = field_validator("window_start")(_require_utc)
    _normalize_end = field_validator("window_end")(_require_utc)

    @model_validator(mode="after")
    def validate_window(self) -> InvestigationCreate:
        duration = self.window_end - self.window_start
        if duration <= timedelta(0):
            raise ValueError("window_end must be later than window_start")
        if duration > timedelta(hours=1):
            raise ValueError("the Phase 1 request window is limited to 60 minutes")
        return self


class InvestigationAccepted(BaseModel):
    investigation_id: UUID
    status: InvestigationStatus
    created_at: datetime


class InvestigationRecord(InvestigationAccepted):
    owner_id: str
    request_id: UUID
    question: str
    target_service: str
    environment: str
    window_start: datetime
    window_end: datetime
    mode: InvestigationMode
    updated_at: datetime


class EventRecord(BaseModel):
    investigation_id: UUID
    sequence: int = Field(ge=1)
    kind: str = Field(min_length=1, max_length=128)
    payload: dict[str, Any]
    created_at: datetime


class JobLease(BaseModel):
    job_id: int
    investigation_id: UUID
    lease_owner: str
    lease_token: UUID
    attempt: int = Field(ge=1)
    leased_until: datetime


class EvidenceItem(BaseModel):
    evidence_id: UUID
    kind: Literal["document", "metric", "log", "topology", "change", "reviewed_incident"]
    source_id: str
    source_version: str
    service_ids: list[str]
    environment: str
    observed_at: datetime
    collected_at: datetime
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    freshness_status: Literal["fresh", "stale", "unknown"]
    limitations: list[str] = Field(default_factory=list)
    provenance_reference: str


class ErrorResponse(BaseModel):
    code: Literal[
        "NOT_FOUND",
        "AMBIGUOUS_SERVICE",
        "UNAUTHORIZED",
        "TIMEOUT",
        "UNAVAILABLE",
        "INVALID_ARGUMENT",
        "INSUFFICIENT_DATA",
    ]
    message: str
    request_id: UUID | None = None
