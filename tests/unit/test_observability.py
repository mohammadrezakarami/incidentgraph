from __future__ import annotations

import json
from pathlib import Path

from incidentgraph.auth import hash_token
from incidentgraph.config import Settings
from incidentgraph.observability import (
    configure_observability,
    current_traceparent,
    parent_context,
    redact,
    tracer,
)


def _settings(trace_dir: Path) -> Settings:
    return Settings(  # type: ignore[call-arg]
        environment="test",
        app_database_dsn="postgresql://app:test@localhost/app",
        lab_database_dsn="postgresql://lab:test@localhost/lab",
        neo4j_uri="bolt://localhost:7687",
        neo4j_password="test-only-password",
        auth_tokens_json=json.dumps(
            {
                hash_token("test-token"): {
                    "principal_id": "viewer-1",
                    "roles": ["viewer"],
                    "service_ids": ["svc-gateway"],
                }
            }
        ),
        observability_tracing_enabled=True,
        observability_trace_dir=trace_dir,
    )


def test_recursive_redaction_covers_keys_bearers_assignments_and_dsn() -> None:
    value = redact(
        {
            "authorization": "Bearer direct-secret",
            "nested": [
                "Authorization=hidden-value",
                "postgresql://user:database-password@localhost/db",
                "safe text",
            ],
        }
    )

    rendered = json.dumps(value)
    assert "direct-secret" not in rendered
    assert "hidden-value" not in rendered
    assert "database-password" not in rendered
    assert "safe text" in rendered


def test_local_trace_export_is_correlated_and_redacted(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    configure_observability(settings, "phase8-test")

    with tracer().start_as_current_span(
        "incidentgraph.api.request",
        attributes={"authorization": "Bearer span-secret"},
    ) as root:
        traceparent = current_traceparent()
        root_trace_id = root.get_span_context().trace_id
    assert traceparent is not None

    with tracer().start_as_current_span(
        "incidentgraph.worker.attempt",
        context=parent_context(traceparent),
        attributes={"safe": "password=span-password"},
    ) as child:
        assert child.get_span_context().trace_id == root_trace_id

    rows = [json.loads(line) for line in (tmp_path / "phase8-test.jsonl").read_text().splitlines()]
    assert {row["name"] for row in rows} == {
        "incidentgraph.api.request",
        "incidentgraph.worker.attempt",
    }
    assert len({row["trace_id"] for row in rows}) == 1
    rendered = json.dumps(rows)
    assert "span-secret" not in rendered
    assert "span-password" not in rendered
    assert rendered.count("[REDACTED]") >= 2
