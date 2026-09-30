import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal, Protocol, cast
from uuid import UUID

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field, model_validator

from incidentgraph.api_support import (
    LocalRateLimiter,
    RateLimitExceeded,
    authorized_services,
    dependency_view,
    encode_sse,
)
from incidentgraph.auth import Principal, TokenAuthenticator, principal_dependency
from incidentgraph.config import Settings
from incidentgraph.ingestion import load_topology
from incidentgraph.investigation_tools import CAPTURE_ROOT, SNAPSHOT_PATTERN
from incidentgraph.logging import configure_logging
from incidentgraph.models import (
    CancellationRecord,
    DependencyView,
    EventRecord,
    EvidenceItem,
    FollowUpCreate,
    FollowUpRecord,
    InvestigationAccepted,
    InvestigationCreate,
    InvestigationMode,
    InvestigationPage,
    InvestigationRecord,
    ReportView,
    ReviewRecord,
    ReviewSubmission,
    ServiceSummary,
)
from incidentgraph.observability import (
    configure_observability,
    current_traceparent,
    observe_process_rss,
    record_api_request,
    tracer,
)
from incidentgraph.persistence import (
    Database,
    DurableConflictError,
    ReviewAuthorizationError,
)


class InvestigationSubmission(InvestigationCreate):
    snapshot_id: str | None = Field(default=None, pattern=SNAPSHOT_PATTERN.pattern)

    @model_validator(mode="after")
    def validate_observation_source(self) -> "InvestigationSubmission":
        if self.mode != InvestigationMode.REPLAY:
            raise ValueError("interactive investigations currently require replay mode")
        if self.snapshot_id is None:
            raise ValueError("snapshot_id is required for replay mode")
        return self


class ReplaySnapshotSummary(BaseModel):
    snapshot_id: str
    observation_start: datetime
    observation_cutoff: datetime
    services: list[str]
    provenance_category: str
    limitations: list[str]


class RepositoryProtocol(Protocol):
    async def ping(self) -> bool: ...

    async def create_investigation(
        self,
        *,
        owner_id: str,
        request_id: UUID,
        idempotency_key: str,
        request: InvestigationCreate,
        authorized_service_ids: tuple[str, ...] = (),
        corpus_version: str = "",
        traceparent: str | None = None,
    ) -> InvestigationAccepted: ...

    async def get_investigation(
        self, investigation_id: UUID, owner_id: str, allow_operator: bool = False
    ) -> InvestigationRecord | None: ...

    async def list_investigations(
        self,
        owner_id: str,
        *,
        allow_operator: bool = False,
        limit: int = 25,
        cursor: UUID | None = None,
    ) -> InvestigationPage: ...

    async def list_events(
        self,
        investigation_id: UUID,
        owner_id: str,
        *,
        allow_operator: bool = False,
        after_sequence: int = 0,
        limit: int = 100,
    ) -> list[EventRecord]: ...

    async def get_report_view(
        self,
        investigation_id: UUID,
        owner_id: str,
        *,
        allow_operator: bool = False,
    ) -> ReportView | None: ...

    async def get_evidence_authorized(
        self,
        investigation_id: UUID,
        evidence_id: UUID,
        owner_id: str,
        *,
        allow_operator: bool = False,
    ) -> EvidenceItem | None: ...

    async def submit_review(
        self,
        investigation_id: UUID,
        *,
        reviewer_id: str,
        roles: frozenset[str],
        idempotency_key: str,
        submission: ReviewSubmission,
    ) -> ReviewRecord: ...

    async def request_cancellation(
        self,
        investigation_id: UUID,
        *,
        owner_id: str,
        allow_operator: bool = False,
    ) -> CancellationRecord: ...

    async def create_follow_up(
        self,
        investigation_id: UUID,
        *,
        owner_id: str,
        idempotency_key: str,
        request: FollowUpCreate,
        allow_operator: bool = False,
    ) -> FollowUpRecord: ...


def create_app(
    settings: Settings | None = None,
    repository: RepositoryProtocol | None = None,
    capture_root: Path = CAPTURE_ROOT,
) -> FastAPI:
    app_settings = settings or Settings()  # type: ignore[call-arg]
    authenticator = TokenAuthenticator(app_settings.auth_tokens)
    require_principal = principal_dependency(authenticator)
    limiter = LocalRateLimiter(app_settings.api_rate_limit_per_minute)
    topology = load_topology()
    managed_database: Database | None = None

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        nonlocal managed_database
        configure_logging(app_settings.log_level)
        configure_observability(app_settings, "incidentgraph-api")
        if repository is None:
            managed_database = Database(app_settings.app_database_dsn.get_secret_value())
            await managed_database.open()
            app.state.repository = managed_database
        else:
            app.state.repository = repository
        yield
        if managed_database is not None:
            await managed_database.close()

    app = FastAPI(
        title="IncidentGraph API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if app_settings.environment == "local" else None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[app_settings.frontend_origin],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Idempotency-Key",
            "Last-Event-ID",
            "X-Request-ID",
        ],
        expose_headers=["Last-Event-ID", "Retry-After", "X-Request-ID"],
    )

    @app.middleware("http")
    async def observe_request(request: Request, call_next: Any) -> Response:
        started = time.perf_counter()
        status_code = 500
        with tracer().start_as_current_span(
            "incidentgraph.api.request",
            attributes={"http.request.method": request.method},
        ) as span:
            try:
                response = cast(Response, await call_next(request))
                status_code = response.status_code
                return response
            finally:
                route = request.scope.get("route")
                route_path = getattr(route, "path", "unmatched")
                span.set_attribute("http.route", route_path)
                span.set_attribute("http.response.status_code", status_code)
                request_id = getattr(request.state, "request_id", None)
                if request_id:
                    span.set_attribute("incidentgraph.request_id", request_id)
                record_api_request(
                    request.method,
                    route_path,
                    status_code,
                    time.perf_counter() - started,
                )
                observe_process_rss("api")

    def error_payload(request: Request, code: str, message: str, retryable: bool) -> dict[str, Any]:
        return {
            "error": {
                "code": code,
                "message": message,
                "request_id": getattr(request.state, "request_id", None),
                "retryable": retryable,
            }
        }

    @app.middleware("http")
    async def request_guard(request: Request, call_next: Any) -> Response:
        supplied = request.headers.get("X-Request-ID")
        try:
            request_id = str(UUID(supplied)) if supplied else str(uuid.uuid4())
        except ValueError:
            request_id = str(uuid.uuid4())
            request.state.request_id = request_id
            response = JSONResponse(
                error_payload(request, "INVALID_ARGUMENT", "X-Request-ID must be a UUID", False),
                status_code=422,
            )
            response.headers["X-Request-ID"] = request_id
            return response
        request.state.request_id = request_id
        content_length = request.headers.get("Content-Length")
        try:
            declared_length = int(content_length) if content_length else 0
        except ValueError:
            response = JSONResponse(
                error_payload(
                    request, "INVALID_ARGUMENT", "Content-Length must be an integer", False
                ),
                status_code=422,
            )
        else:
            if declared_length < 0:
                response = JSONResponse(
                    error_payload(
                        request, "INVALID_ARGUMENT", "Content-Length cannot be negative", False
                    ),
                    status_code=422,
                )
            elif declared_length > app_settings.api_max_request_bytes:
                response = JSONResponse(
                    error_payload(request, "PAYLOAD_TOO_LARGE", "request body is too large", False),
                    status_code=413,
                )
            else:
                bounded_body = bytearray()
                body_too_large = False
                async for chunk in request.stream():
                    if len(bounded_body) + len(chunk) > app_settings.api_max_request_bytes:
                        body_too_large = True
                        break
                    bounded_body.extend(chunk)
                if body_too_large:
                    response = JSONResponse(
                        error_payload(
                            request, "PAYLOAD_TOO_LARGE", "request body is too large", False
                        ),
                        status_code=413,
                    )
                else:
                    request._body = bytes(bounded_body)
                    response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        code = {
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            409: "CONFLICT",
            413: "PAYLOAD_TOO_LARGE",
            422: "INVALID_ARGUMENT",
            429: "RATE_LIMITED",
            503: "UNAVAILABLE",
        }.get(exc.status_code, "REQUEST_FAILED")
        response = JSONResponse(
            error_payload(
                request,
                code,
                str(exc.detail),
                exc.status_code in {429, 503},
            ),
            status_code=exc.status_code,
            headers=exc.headers,
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            error_payload(request, "INVALID_ARGUMENT", "request validation failed", False)
            | {"details": json.loads(json.dumps(exc.errors(), default=str))},
            status_code=422,
        )

    def repo(request: Request) -> RepositoryProtocol:
        return cast(RepositoryProtocol, request.app.state.repository)

    def api_principal(
        principal: Annotated[Principal, Depends(require_principal)],
    ) -> Principal:
        try:
            limiter.check(principal.principal_id)
        except RateLimitExceeded as exc:
            raise HTTPException(
                status_code=429,
                detail=str(exc),
                headers={"Retry-After": "60"},
            ) from exc
        return principal

    def is_operator(principal: Principal) -> bool:
        return "operator" in principal.roles

    def resolve_target_service(value: str, principal: Principal) -> str | None:
        normalized = value.casefold()
        for item in topology.services:
            candidates = {item.id.casefold(), item.name.casefold()}
            candidates.update(alias.casefold() for alias in item.aliases)
            if item.id in principal.service_ids and normalized in candidates:
                return item.id
        return None

    def replay_snapshots(principal: Principal) -> list[ReplaySnapshotSummary]:
        root = capture_root.resolve()
        if not root.is_dir():
            return []
        snapshots: list[ReplaySnapshotSummary] = []
        for directory in root.iterdir():
            if (
                not directory.is_dir()
                or directory.is_symlink()
                or not SNAPSHOT_PATTERN.fullmatch(directory.name)
            ):
                continue
            try:
                manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
                services = [f"svc-{name}" for name in manifest["services"]]
                snapshot = ReplaySnapshotSummary(
                    snapshot_id=directory.name,
                    observation_start=manifest["observation_start"],
                    observation_cutoff=manifest["observation_cutoff"],
                    services=services,
                    provenance_category=str(manifest["provenance_category"]),
                    limitations=[str(item) for item in manifest.get("limitations", [])],
                )
            except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
                continue
            if set(snapshot.services).intersection(principal.service_ids):
                snapshots.append(snapshot)
        return sorted(snapshots, key=lambda item: item.observation_cutoff, reverse=True)[:50]

    @app.get("/health/live")
    async def liveness() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    async def readiness(
        repository_dependency: Annotated[RepositoryProtocol, Depends(repo)],
    ) -> dict[str, str]:
        if not await repository_dependency.ping():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="database unavailable",
            )
        return {"status": "ready"}

    @app.get("/api/v1/replay-snapshots", response_model=list[ReplaySnapshotSummary])
    async def list_replay_snapshots(
        principal: Annotated[Principal, Depends(api_principal)],
    ) -> list[ReplaySnapshotSummary]:
        return replay_snapshots(principal)

    @app.post(
        "/api/v1/investigations",
        response_model=InvestigationAccepted,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def create_investigation(
        body: InvestigationSubmission,
        request: Request,
        principal: Annotated[Principal, Depends(api_principal)],
        repository_dependency: Annotated[RepositoryProtocol, Depends(repo)],
        idempotency_key: Annotated[
            str,
            Header(alias="Idempotency-Key", min_length=8, max_length=128),
        ],
    ) -> InvestigationAccepted:
        service_id = resolve_target_service(body.target_service, principal)
        if service_id is None:
            raise HTTPException(status_code=403, detail="target service is outside authorization")
        if app_settings.model_provider == "disabled":
            raise HTTPException(
                status_code=503,
                detail="model provider is disabled; configure an approved provider before starting",
            )
        model_configuration_problems = [
            problem
            for problem in app_settings.validate_runtime()
            if problem.startswith(("MODEL_", "local MODEL_"))
        ]
        if model_configuration_problems:
            raise HTTPException(
                status_code=503,
                detail=(
                    f"model provider configuration is invalid: {model_configuration_problems[0]}"
                ),
            )
        snapshot = next(
            (item for item in replay_snapshots(principal) if item.snapshot_id == body.snapshot_id),
            None,
        )
        if snapshot is None:
            raise HTTPException(status_code=404, detail="replay snapshot was not found")
        if service_id not in snapshot.services:
            raise HTTPException(
                status_code=422, detail="target service is absent from the snapshot"
            )
        if (
            body.window_start != snapshot.observation_start
            or body.window_end != snapshot.observation_cutoff
        ):
            raise HTTPException(
                status_code=422,
                detail="replay window must exactly match the immutable snapshot window",
            )
        request_id = UUID(request.state.request_id)
        normalized_body = body.model_copy(update={"target_service": service_id})
        return await repository_dependency.create_investigation(
            owner_id=principal.principal_id,
            request_id=request_id,
            idempotency_key=idempotency_key,
            request=normalized_body,
            authorized_service_ids=tuple(sorted(principal.service_ids)),
            corpus_version=app_settings.corpus_id,
            traceparent=current_traceparent(),
        )

    @app.get("/api/v1/investigations", response_model=InvestigationPage)
    async def list_investigations(
        principal: Annotated[Principal, Depends(api_principal)],
        repository_dependency: Annotated[RepositoryProtocol, Depends(repo)],
        limit: Annotated[int, Query(ge=1)] = 25,
        cursor: UUID | None = None,
    ) -> InvestigationPage:
        return await repository_dependency.list_investigations(
            principal.principal_id,
            allow_operator=is_operator(principal),
            limit=min(limit, app_settings.api_page_size_max),
            cursor=cursor,
        )

    @app.get("/api/v1/investigations/{investigation_id}", response_model=InvestigationRecord)
    async def get_investigation(
        investigation_id: UUID,
        principal: Annotated[Principal, Depends(api_principal)],
        repository_dependency: Annotated[RepositoryProtocol, Depends(repo)],
    ) -> InvestigationRecord:
        record = await repository_dependency.get_investigation(
            investigation_id,
            principal.principal_id,
            allow_operator=is_operator(principal),
        )
        if record is None:
            raise HTTPException(status_code=404, detail="investigation not found")
        return record

    @app.get("/api/v1/investigations/{investigation_id}/events")
    async def stream_events(
        investigation_id: UUID,
        request: Request,
        principal: Annotated[Principal, Depends(api_principal)],
        repository_dependency: Annotated[RepositoryProtocol, Depends(repo)],
        last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
    ) -> StreamingResponse:
        record = await repository_dependency.get_investigation(
            investigation_id,
            principal.principal_id,
            allow_operator=is_operator(principal),
        )
        if record is None:
            raise HTTPException(status_code=404, detail="investigation not found")
        try:
            after_sequence = int(last_event_id) if last_event_id else 0
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Last-Event-ID must be an integer") from exc
        if after_sequence < 0:
            raise HTTPException(status_code=422, detail="Last-Event-ID cannot be negative")

        async def events() -> AsyncIterator[bytes]:
            sequence = after_sequence
            started = time.monotonic()
            last_output = started
            terminal = {"completed", "inconclusive", "failed", "cancelled"}
            while time.monotonic() - started < app_settings.sse_max_connection_seconds:
                if await request.is_disconnected():
                    return
                records = await repository_dependency.list_events(
                    investigation_id,
                    principal.principal_id,
                    allow_operator=is_operator(principal),
                    after_sequence=sequence,
                    limit=100,
                )
                for event in records:
                    sequence = event.sequence
                    last_output = time.monotonic()
                    yield encode_sse(event)
                current = await repository_dependency.get_investigation(
                    investigation_id,
                    principal.principal_id,
                    allow_operator=is_operator(principal),
                )
                if current is None or (current.status.value in terminal and not records):
                    return
                if time.monotonic() - last_output >= app_settings.sse_heartbeat_seconds:
                    last_output = time.monotonic()
                    yield b": heartbeat\n\n"
                await asyncio.sleep(app_settings.sse_poll_interval_seconds)

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get(
        "/api/v1/investigations/{investigation_id}/report",
        response_model=ReportView,
    )
    async def get_report(
        investigation_id: UUID,
        principal: Annotated[Principal, Depends(api_principal)],
        repository_dependency: Annotated[RepositoryProtocol, Depends(repo)],
    ) -> ReportView:
        report = await repository_dependency.get_report_view(
            investigation_id,
            principal.principal_id,
            allow_operator=is_operator(principal),
        )
        if report is None:
            raise HTTPException(status_code=404, detail="report not found")
        return report

    @app.get(
        "/api/v1/investigations/{investigation_id}/evidence/{evidence_id}",
        response_model=EvidenceItem,
    )
    async def get_evidence(
        investigation_id: UUID,
        evidence_id: UUID,
        principal: Annotated[Principal, Depends(api_principal)],
        repository_dependency: Annotated[RepositoryProtocol, Depends(repo)],
    ) -> EvidenceItem:
        evidence = await repository_dependency.get_evidence_authorized(
            investigation_id,
            evidence_id,
            principal.principal_id,
            allow_operator=is_operator(principal),
        )
        if evidence is None:
            raise HTTPException(status_code=404, detail="evidence not found")
        return evidence

    @app.post(
        "/api/v1/investigations/{investigation_id}/reviews",
        response_model=ReviewRecord,
    )
    async def submit_review(
        investigation_id: UUID,
        body: ReviewSubmission,
        principal: Annotated[Principal, Depends(api_principal)],
        repository_dependency: Annotated[RepositoryProtocol, Depends(repo)],
        idempotency_key: Annotated[
            str,
            Header(alias="Idempotency-Key", min_length=8, max_length=128),
        ],
    ) -> ReviewRecord:
        if not principal.roles.intersection({"reviewer", "operator"}):
            raise HTTPException(status_code=403, detail="reviewer or operator role required")
        investigation = await repository_dependency.get_investigation(
            investigation_id,
            principal.principal_id,
            allow_operator=is_operator(principal),
        )
        if investigation is None:
            raise HTTPException(status_code=404, detail="investigation not found")
        try:
            return await repository_dependency.submit_review(
                investigation_id,
                reviewer_id=principal.principal_id,
                roles=principal.roles,
                idempotency_key=idempotency_key,
                submission=body,
            )
        except ReviewAuthorizationError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except DurableConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post(
        "/api/v1/investigations/{investigation_id}/cancel",
        response_model=CancellationRecord,
    )
    async def cancel_investigation(
        investigation_id: UUID,
        principal: Annotated[Principal, Depends(api_principal)],
        repository_dependency: Annotated[RepositoryProtocol, Depends(repo)],
    ) -> CancellationRecord:
        try:
            return await repository_dependency.request_cancellation(
                investigation_id,
                owner_id=principal.principal_id,
                allow_operator=is_operator(principal),
            )
        except DurableConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post(
        "/api/v1/investigations/{investigation_id}/followups",
        response_model=FollowUpRecord,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def create_follow_up(
        investigation_id: UUID,
        body: FollowUpCreate,
        principal: Annotated[Principal, Depends(api_principal)],
        repository_dependency: Annotated[RepositoryProtocol, Depends(repo)],
        idempotency_key: Annotated[
            str,
            Header(alias="Idempotency-Key", min_length=8, max_length=128),
        ],
    ) -> FollowUpRecord:
        try:
            return await repository_dependency.create_follow_up(
                investigation_id,
                owner_id=principal.principal_id,
                idempotency_key=idempotency_key,
                request=body,
                allow_operator=is_operator(principal),
            )
        except DurableConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/v1/services", response_model=list[ServiceSummary])
    async def list_services(
        principal: Annotated[Principal, Depends(api_principal)],
    ) -> list[ServiceSummary]:
        return authorized_services(topology, principal.service_ids)

    @app.get(
        "/api/v1/services/{service_id}/dependencies",
        response_model=DependencyView,
    )
    async def get_dependencies(
        service_id: str,
        principal: Annotated[Principal, Depends(api_principal)],
        cutoff: datetime | None = None,
        direction: Literal["inbound", "outbound", "both"] = "both",
        depth: Annotated[int, Query(ge=1, le=2)] = 1,
    ) -> DependencyView:
        resolved_service_id = resolve_target_service(service_id, principal)
        if resolved_service_id is None:
            raise HTTPException(status_code=404, detail="service not found")
        effective_cutoff = cutoff or datetime.now(UTC)
        if effective_cutoff.tzinfo is None or effective_cutoff.utcoffset() is None:
            raise HTTPException(status_code=422, detail="cutoff must include a UTC offset")
        view = dependency_view(
            topology,
            service_id=resolved_service_id,
            authorized_service_ids=principal.service_ids,
            cutoff=effective_cutoff,
            direction=direction,
            depth=depth,
        )
        if view is None:
            raise HTTPException(status_code=404, detail="dependency view not found at cutoff")
        return view

    @app.get("/metrics")
    async def internal_metrics(
        principal: Annotated[Principal, Depends(api_principal)],
    ) -> Response:
        if not is_operator(principal):
            raise HTTPException(status_code=403, detail="operator role required")
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    uvicorn.run(
        create_app(settings),
        host=settings.api_host,
        port=settings.api_port,
        log_config=None,
    )
