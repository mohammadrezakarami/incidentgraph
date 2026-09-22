import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Protocol, cast
from uuid import UUID

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware

from incidentgraph.auth import Principal, TokenAuthenticator, principal_dependency
from incidentgraph.config import Settings
from incidentgraph.logging import configure_logging
from incidentgraph.models import (
    EventRecord,
    InvestigationAccepted,
    InvestigationCreate,
    InvestigationRecord,
)
from incidentgraph.persistence import Database


class RepositoryProtocol(Protocol):
    async def ping(self) -> bool: ...

    async def create_investigation(
        self,
        *,
        owner_id: str,
        request_id: UUID,
        idempotency_key: str,
        request: InvestigationCreate,
    ) -> InvestigationAccepted: ...

    async def get_investigation(
        self, investigation_id: UUID, owner_id: str
    ) -> InvestigationRecord | None: ...

    async def list_events(self, investigation_id: UUID, owner_id: str) -> list[EventRecord]: ...


def create_app(
    settings: Settings | None = None,
    repository: RepositoryProtocol | None = None,
) -> FastAPI:
    app_settings = settings or Settings()  # type: ignore[call-arg]
    authenticator = TokenAuthenticator(app_settings.auth_tokens)
    require_principal = principal_dependency(authenticator)
    managed_database: Database | None = None

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        nonlocal managed_database
        configure_logging(app_settings.log_level)
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
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
    )

    def repo(request: Request) -> RepositoryProtocol:
        return cast(RepositoryProtocol, request.app.state.repository)

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

    @app.post(
        "/api/v1/investigations",
        response_model=InvestigationAccepted,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def create_investigation(
        body: InvestigationCreate,
        principal: Annotated[Principal, Depends(require_principal)],
        repository_dependency: Annotated[RepositoryProtocol, Depends(repo)],
        idempotency_key: Annotated[
            str,
            Header(alias="Idempotency-Key", min_length=8, max_length=128),
        ],
        request_id_header: Annotated[str | None, Header(alias="X-Request-ID")] = None,
    ) -> InvestigationAccepted:
        try:
            request_id = UUID(request_id_header) if request_id_header else uuid.uuid4()
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="X-Request-ID must be a UUID") from exc
        return await repository_dependency.create_investigation(
            owner_id=principal.principal_id,
            request_id=request_id,
            idempotency_key=idempotency_key,
            request=body,
        )

    @app.get("/api/v1/investigations/{investigation_id}", response_model=InvestigationRecord)
    async def get_investigation(
        investigation_id: UUID,
        principal: Annotated[Principal, Depends(require_principal)],
        repository_dependency: Annotated[RepositoryProtocol, Depends(repo)],
    ) -> InvestigationRecord:
        record = await repository_dependency.get_investigation(
            investigation_id,
            principal.principal_id,
        )
        if record is None:
            raise HTTPException(status_code=404, detail="investigation not found")
        return record

    @app.get("/api/v1/investigations/{investigation_id}/events", response_model=list[EventRecord])
    async def list_events(
        investigation_id: UUID,
        principal: Annotated[Principal, Depends(require_principal)],
        repository_dependency: Annotated[RepositoryProtocol, Depends(repo)],
    ) -> list[EventRecord]:
        return list(
            await repository_dependency.list_events(
                investigation_id,
                principal.principal_id,
            )
        )

    return app


def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    uvicorn.run(
        create_app(settings),
        host=settings.api_host,
        port=settings.api_port,
        log_config=None,
    )
