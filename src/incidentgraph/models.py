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
    generation: int = Field(default=1, ge=1)
    task_kind: Literal[
        "investigation", "review_resume", "review_revision", "follow_up"
    ] = "investigation"
    target_report_version: int = Field(default=1, ge=1)


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
    window_start: datetime | None = None
    window_end: datetime | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    snapshot_id: str | None = None
    query_template_id: str | None = None
    safe_parameters: dict[str, Any] = Field(default_factory=dict)
    content: str | None = None
    unit: str | None = None
    aggregation: str | None = None


class EvidenceStrength(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReportOutcome(StrEnum):
    PROBABLE_CAUSE = "probable_cause"
    INCONCLUSIVE = "inconclusive"
    NO_INCIDENT_DETECTED = "no_incident_detected"


class ReviewStatus(StrEnum):
    NOT_REQUESTED = "not_requested"
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    REVISION_REQUESTED = "revision_requested"
    EXPIRED = "expired"


class ReviewDecision(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"
    REQUEST_REVISION = "request_revision"


class ReviewSubmission(BaseModel):
    report_version: int = Field(ge=1)
    decision: ReviewDecision
    rationale: str = Field(min_length=3, max_length=2_000)


class ReviewRecord(BaseModel):
    review_id: UUID
    investigation_id: UUID
    report_version: int = Field(ge=1)
    status: ReviewStatus
    reviewer_id: str | None = None
    requested_at: datetime
    expires_at: datetime
    decided_at: datetime | None = None


class FollowUpCreate(BaseModel):
    question: str = Field(min_length=8, max_length=2_000)
    max_model_calls: int = Field(ge=1, le=20)
    max_tool_calls: int = Field(ge=1, le=32)


class FollowUpRecord(BaseModel):
    follow_up_id: UUID
    investigation_id: UUID
    base_report_version: int = Field(ge=1)
    target_report_version: int = Field(ge=2)
    status: InvestigationStatus
    created_at: datetime


class CancellationRecord(BaseModel):
    investigation_id: UUID
    status: InvestigationStatus
    cancellation_requested_at: datetime


class PublicationResult(BaseModel):
    investigation_id: UUID
    report_version: int = Field(ge=1)
    status: InvestigationStatus
    duplicate: bool
    review_id: UUID | None = None


class IncidentWindow(BaseModel):
    start: datetime
    end: datetime

    _normalize_start = field_validator("start")(_require_utc)
    _normalize_end = field_validator("end")(_require_utc)

    @model_validator(mode="after")
    def validate_interval(self) -> IncidentWindow:
        if self.end <= self.start:
            raise ValueError("incident window end must be later than start")
        return self


class RankedHypothesis(BaseModel):
    rank: int = Field(ge=1, le=3)
    mechanism: str = Field(min_length=3, max_length=200)
    suspected_component: str = Field(min_length=1, max_length=128)
    evidence_strength: EvidenceStrength
    supporting_evidence_ids: list[UUID]
    contradicting_evidence_ids: list[UUID] = Field(default_factory=list)
    explanation_summary: str = Field(min_length=3, max_length=2_000)
    additional_evidence_needed: list[str] = Field(default_factory=list, max_length=10)


class ImpactStatement(BaseModel):
    description: str = Field(min_length=3, max_length=1_000)
    evidence_ids: list[UUID]


class RecommendedNextStep(BaseModel):
    description: str = Field(min_length=3, max_length=1_000)
    rationale: str = Field(min_length=3, max_length=1_000)
    evidence_ids: list[UUID]
    risk_level: Literal["low", "medium", "high"]
    preconditions: list[str] = Field(default_factory=list, max_length=10)
    verification_steps: list[str] = Field(default_factory=list, max_length=10)
    rollback_considerations: list[str] = Field(default_factory=list, max_length=10)
    execution_status: Literal["not_executed"] = "not_executed"


class UsageAndTiming(BaseModel):
    model_calls: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    active_duration_ms: float = Field(ge=0)
    model_latency_ms: float = Field(ge=0)
    tool_latency_ms: float = Field(ge=0)
    cost_is_estimate: bool = True


class InvestigationReport(BaseModel):
    investigation_id: UUID
    report_version: int = Field(ge=1)
    mode: InvestigationMode
    snapshot_id: str | None
    target_service: str
    environment: str
    incident_window: IncidentWindow
    observation_cutoff: datetime
    outcome: ReportOutcome
    summary: str = Field(min_length=3, max_length=4_000)
    observed_symptoms: list[ImpactStatement] = Field(default_factory=list, max_length=20)
    ranked_hypotheses: list[RankedHypothesis] = Field(default_factory=list, max_length=3)
    observed_impact: list[ImpactStatement] = Field(default_factory=list, max_length=20)
    potential_impact: list[ImpactStatement] = Field(default_factory=list, max_length=20)
    recommended_next_steps: list[RecommendedNextStep] = Field(default_factory=list, max_length=10)
    limitations: list[str] = Field(default_factory=list, max_length=20)
    review_status: ReviewStatus = ReviewStatus.NOT_REQUESTED
    termination_reason: str = Field(min_length=1, max_length=200)
    usage_and_timing: UsageAndTiming
    trace_reference: str

    _normalize_cutoff = field_validator("observation_cutoff")(_require_utc)

    @model_validator(mode="after")
    def validate_report_shape(self) -> InvestigationReport:
        ranks = [item.rank for item in self.ranked_hypotheses]
        if ranks != list(range(1, len(ranks) + 1)):
            raise ValueError("hypothesis ranks must be contiguous and start at one")
        if self.outcome == ReportOutcome.PROBABLE_CAUSE and not self.ranked_hypotheses:
            raise ValueError("probable_cause requires at least one ranked hypothesis")
        if self.outcome == ReportOutcome.INCONCLUSIVE and not self.limitations:
            raise ValueError("inconclusive reports must state limitations")
        return self


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
