import json

import pytest
from pydantic import ValidationError

from incidentgraph.auth import hash_token
from incidentgraph.config import Settings


def settings_kwargs() -> dict[str, object]:
    return {
        "environment": "test",
        "app_database_dsn": "postgresql://app:test@localhost/app",
        "lab_database_dsn": "postgresql://lab:test@localhost/lab",
        "neo4j_uri": "bolt://localhost:7687",
        "neo4j_password": "test-only-password",
        "auth_tokens_json": json.dumps(
            {
                hash_token("test-token"): {
                    "principal_id": "viewer-1",
                    "roles": ["viewer"],
                }
            }
        ),
    }


def test_settings_parse_principals_and_disable_models_by_default() -> None:
    settings = Settings(**settings_kwargs())

    assert len(settings.auth_tokens) == 1
    assert settings.model_provider == "disabled"
    assert settings.validate_runtime() == []


def test_non_loopback_bind_is_rejected() -> None:
    values = settings_kwargs() | {"api_host": "0.0.0.0"}

    with pytest.raises(ValidationError, match="loopback"):
        Settings(**values)


def test_enabled_provider_requires_model_and_budget() -> None:
    values = settings_kwargs() | {"model_provider": "openai"}
    settings = Settings(**values)

    assert "MODEL_ID is required" in " ".join(settings.validate_runtime())
    assert "MODEL_COST_CEILING_USD" in " ".join(settings.validate_runtime())


def test_embedding_revision_and_dimension_are_validated() -> None:
    values = settings_kwargs() | {
        "embedding_model_revision": "main",
        "embedding_dimension": 768,
    }
    settings = Settings(**values)

    problems = " ".join(settings.validate_runtime())
    assert "full lowercase Git commit SHA" in problems
    assert "requires EMBEDDING_DIMENSION=384" in problems
