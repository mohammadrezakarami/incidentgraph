from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from incidentgraph.api import create_app
from incidentgraph.auth import hash_token
from incidentgraph.config import Settings
from incidentgraph.models import (
    EventRecord,
    InvestigationAccepted,
    InvestigationMode,
    InvestigationPage,
    InvestigationRecord,
    InvestigationStatus,
)
from incidentgraph.persistence import DurableConflictError, ReviewAuthorizationError


class FakeRepository:
    def __init__(self) -> None:
        self.created: dict[str, Any] | None = None
        self.record: InvestigationRecord | None = None
        self.events: list[EventRecord] = []

    async def ping(self) -> bool:
        return True

    async def create_investigation(self, **kwargs: Any) -> InvestigationAccepted:
        self.created = kwargs
        return InvestigationAccepted(
            investigation_id=uuid4(),
            status=InvestigationStatus.QUEUED,
            created_at=datetime.now(UTC),
        )

    async def get_investigation(self, *_: Any, **__: Any) -> InvestigationRecord | None:
        return self.record

    async def list_investigations(self, *_: Any, **__: Any) -> InvestigationPage:
        return InvestigationPage(items=[self.record] if self.record else [])

    async def list_events(self, *_: Any, **kwargs: Any) -> list[EventRecord]:
        after = int(kwargs.get("after_sequence", 0))
        return [event for event in self.events if event.sequence > after]

    async def get_report_view(self, *_: Any, **__: Any) -> None:
        return None

    async def get_evidence_authorized(self, *_: Any, **__: Any) -> None:
        return None

    async def submit_review(self, *_: Any, **__: Any) -> Any:
        raise ReviewAuthorizationError("reviewer or operator role required")

    async def request_cancellation(self, *_: Any, **__: Any) -> Any:
        raise DurableConflictError("investigation not found")

    async def create_follow_up(self, *_: Any, **__: Any) -> Any:
        raise DurableConflictError("investigation not found")


def settings_with_tokens(tokens: dict[str, dict[str, Any]], **overrides: Any) -> Settings:
    scoped_tokens = {
        token: value
        | {
            "service_ids": value.get(
                "service_ids", ["svc-gateway", "svc-checkout", "svc-payments"]
            )
        }
        for token, value in tokens.items()
    }
    return Settings(
        environment="test",
        app_database_dsn="postgresql://app:test@localhost/app",
        lab_database_dsn="postgresql://lab:test@localhost/lab",
        neo4j_uri="bolt://localhost:7687",
        neo4j_password="test-only-password",
        auth_tokens_json=json.dumps(
            {hash_token(token): value for token, value in scoped_tokens.items()}
        ),
        **overrides,
    )


def investigation(owner_id: str = "viewer-1") -> InvestigationRecord:
    now = datetime.now(UTC)
    return InvestigationRecord(
        investigation_id=uuid4(),
        owner_id=owner_id,
        request_id=uuid4(),
        question="Why did checkout latency increase during this interval?",
        target_service="svc-checkout",
        environment="lab",
        window_start=now - timedelta(minutes=5),
        window_end=now,
        mode=InvestigationMode.REPLAY,
        status=InvestigationStatus.COMPLETED,
        created_at=now - timedelta(minutes=4),
        updated_at=now,
        current_report_version=1,
    )


def test_unauthorized_creation_is_rejected() -> None:
    settings = Settings(
        environment="test",
        app_database_dsn="postgresql://app:test@localhost/app",
        lab_database_dsn="postgresql://lab:test@localhost/lab",
        neo4j_uri="bolt://localhost:7687",
        neo4j_password="test-only-password",
        auth_tokens_json=json.dumps(
            {
                hash_token("valid-token"): {
                    "principal_id": "viewer-1",
                    "roles": ["viewer"],
                    "service_ids": ["svc-gateway", "svc-checkout", "svc-payments"],
                }
            }
        ),
    )
    now = datetime.now(UTC)
    payload = {
        "question": "Why did checkout latency increase during this interval?",
        "target_service": "checkout",
        "environment": "lab",
        "window_start": (now - timedelta(minutes=5)).isoformat(),
        "window_end": now.isoformat(),
        "mode": "replay",
    }

    with TestClient(create_app(settings, FakeRepository())) as client:
        response = client.post(
            "/api/v1/investigations",
            headers={"Idempotency-Key": "request-0001"},
            json=payload,
        )

    assert response.status_code == 401


def test_liveness_does_not_require_authentication() -> None:
    settings = Settings(
        environment="test",
        app_database_dsn="postgresql://app:test@localhost/app",
        lab_database_dsn="postgresql://lab:test@localhost/lab",
        neo4j_uri="bolt://localhost:7687",
        neo4j_password="test-only-password",
        auth_tokens_json="{}",
    )
    with TestClient(create_app(settings, FakeRepository())) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_viewer_cannot_submit_review_decision() -> None:
    settings = Settings(
        environment="test",
        app_database_dsn="postgresql://app:test@localhost/app",
        lab_database_dsn="postgresql://lab:test@localhost/lab",
        neo4j_uri="bolt://localhost:7687",
        neo4j_password="test-only-password",
        auth_tokens_json=json.dumps(
            {
                hash_token("viewer-token"): {
                    "principal_id": "viewer-1",
                    "roles": ["viewer"],
                    "service_ids": ["svc-gateway", "svc-checkout", "svc-payments"],
                }
            }
        ),
    )
    with TestClient(create_app(settings, FakeRepository())) as client:
        response = client.post(
            f"/api/v1/investigations/{uuid4()}/reviews",
            headers={
                "Authorization": "Bearer viewer-token",
                "Idempotency-Key": "review-request-0001",
            },
            json={
                "report_version": 1,
                "decision": "accept",
                "rationale": "The report is ready for review.",
            },
        )

    assert response.status_code == 403


def test_authorized_creation_normalizes_service_alias_and_uses_request_id() -> None:
    repository = FakeRepository()
    settings = settings_with_tokens(
        {
            "viewer-token": {
                "principal_id": "viewer-1",
                "roles": ["viewer"],
                "service_ids": ["svc-checkout"],
            }
        },
        model_provider="local_openai_compatible",
        model_id="test-model",
        model_base_url="http://127.0.0.1:11434/v1",
    )
    now = datetime.now(UTC)
    request_id = uuid4()
    with TestClient(create_app(settings, repository)) as client:
        response = client.post(
            "/api/v1/investigations",
            headers={
                "Authorization": "Bearer viewer-token",
                "Idempotency-Key": "request-0001",
                "X-Request-ID": str(request_id),
            },
            json={
                "question": "Why did checkout latency increase during this interval?",
                "target_service": "order-coordinator",
                "environment": "lab",
                "window_start": (now - timedelta(minutes=5)).isoformat(),
                "window_end": now.isoformat(),
                "mode": "replay",
            },
        )

    assert response.status_code == 202
    assert response.headers["X-Request-ID"] == str(request_id)
    assert repository.created is not None
    assert repository.created["request"].target_service == "svc-checkout"
    assert repository.created["request_id"] == request_id
    assert repository.created["authorized_service_ids"] == ("svc-checkout",)


def test_creation_fails_cleanly_for_invalid_model_configuration() -> None:
    repository = FakeRepository()
    settings = settings_with_tokens(
        {"viewer-token": {"principal_id": "viewer-1", "roles": ["viewer"]}},
        model_provider="local_openai_compatible",
        model_id="configured-but-missing-base-url",
    )
    now = datetime.now(UTC)
    with TestClient(create_app(settings, repository)) as client:
        response = client.post(
            "/api/v1/investigations",
            headers={
                "Authorization": "Bearer viewer-token",
                "Idempotency-Key": "invalid-model-config",
            },
            json={
                "question": "Why did gateway latency increase during this interval?",
                "target_service": "svc-gateway",
                "environment": "lab",
                "window_start": (now - timedelta(minutes=5)).isoformat(),
                "window_end": now.isoformat(),
                "mode": "replay",
            },
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "UNAVAILABLE"
    assert "MODEL_BASE_URL" in response.json()["error"]["message"]
    assert repository.created is None


def test_service_catalog_and_dependency_view_are_authorization_scoped() -> None:
    settings = settings_with_tokens(
        {
            "viewer-token": {
                "principal_id": "viewer-1",
                "roles": ["viewer"],
                "service_ids": ["svc-checkout", "svc-payments"],
            }
        }
    )
    headers = {"Authorization": "Bearer viewer-token"}
    with TestClient(create_app(settings, FakeRepository())) as client:
        catalog = client.get("/api/v1/services", headers=headers)
        graph = client.get(
            "/api/v1/services/svc-checkout/dependencies",
            params={"cutoff": "2026-09-23T00:00:00Z", "direction": "both", "depth": 2},
            headers=headers,
        )
        forbidden = client.get(
            "/api/v1/services/svc-gateway/dependencies",
            params={"cutoff": "2026-09-23T00:00:00Z"},
            headers=headers,
        )

    assert {item["service_id"] for item in catalog.json()} == {"svc-checkout", "svc-payments"}
    assert graph.status_code == 200
    assert graph.json()["edges"] == [
        {"caller": "svc-checkout", "callee": "svc-payments", "relationship": "DEPENDS_ON"}
    ]
    assert forbidden.status_code == 404


def test_internal_metrics_require_operator_role() -> None:
    settings = settings_with_tokens(
        {
            "viewer-token": {"principal_id": "viewer-1", "roles": ["viewer"]},
            "operator-token": {"principal_id": "operator-1", "roles": ["operator"]},
        }
    )
    with TestClient(create_app(settings, FakeRepository())) as client:
        denied = client.get(
            "/metrics", headers={"Authorization": "Bearer viewer-token"}
        )
        allowed = client.get(
            "/metrics", headers={"Authorization": "Bearer operator-token"}
        )

    assert denied.status_code == 403
    assert allowed.status_code == 200
    assert "python_gc_objects_collected_total" in allowed.text
    assert "incidentgraph_api_requests_total" in allowed.text
    assert "incidentgraph_worker_attempts_total" in allowed.text
    assert "incidentgraph_model_calls_total" in allowed.text
    assert "incidentgraph_tool_calls_total" in allowed.text


def test_sse_resumes_strictly_after_last_event_id() -> None:
    repository = FakeRepository()
    repository.record = investigation()
    now = datetime.now(UTC)
    repository.events = [
        EventRecord(
            investigation_id=repository.record.investigation_id,
            sequence=sequence,
            kind="investigation.event",
            payload={"summary": f"event {sequence}"},
            created_at=now,
        )
        for sequence in (1, 2, 3)
    ]
    settings = settings_with_tokens(
        {"viewer-token": {"principal_id": "viewer-1", "roles": ["viewer"]}}
    )
    with TestClient(create_app(settings, repository)) as client:
        response = client.get(
            f"/api/v1/investigations/{repository.record.investigation_id}/events",
            headers={"Authorization": "Bearer viewer-token", "Last-Event-ID": "2"},
        )

    assert response.status_code == 200
    assert "id: 3" in response.text
    assert "id: 1" not in response.text
    assert "id: 2" not in response.text


def test_oversized_request_is_rejected_before_route_handling() -> None:
    settings = settings_with_tokens({}, api_max_request_bytes=1024)
    with TestClient(create_app(settings, FakeRepository())) as client:
        response = client.post(
            "/api/v1/investigations",
            headers={"Content-Length": "2048"},
            content=b"{}",
        )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert UUID(response.headers["X-Request-ID"])
