from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient

from incidentgraph.api import create_app
from incidentgraph.auth import hash_token
from incidentgraph.config import Settings
from incidentgraph.persistence import ReviewAuthorizationError


class FakeRepository:
    async def ping(self) -> bool:
        return True

    async def create_investigation(self, **_: Any) -> Any:
        raise AssertionError("unauthorized request must not reach persistence")

    async def get_investigation(self, *_: Any) -> None:
        return None

    async def list_events(self, *_: Any) -> list[Any]:
        return []

    async def submit_review(self, *_: Any, **__: Any) -> Any:
        raise ReviewAuthorizationError("reviewer or operator role required")


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
