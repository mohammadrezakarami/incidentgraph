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
                    "service_ids": ["svc-gateway"],
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


def test_container_bind_and_internal_free_model_endpoint_are_explicitly_allowed() -> None:
    values = settings_kwargs() | {
        "environment": "container",
        "api_host": "0.0.0.0",
        "model_provider": "local_openai_compatible",
        "model_id": "local-test-model",
        "model_base_url": "http://ollama:11434/v1",
        "model_cost_ceiling_usd": 0,
    }

    settings = Settings(**values)

    assert settings.validate_runtime() == []


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


def test_free_local_provider_requires_loopback_and_zero_cost() -> None:
    values = settings_kwargs() | {
        "model_provider": "local_openai_compatible",
        "model_id": "local-test-model",
        "model_base_url": "https://remote.example.invalid/v1",
        "model_cost_ceiling_usd": 1,
    }
    configured = Settings(**values)

    problems = " ".join(configured.validate_runtime())

    assert "loopback" in problems
    assert "keep MODEL_COST_CEILING_USD at zero" in problems


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost.example.invalid/v1",
        "http://127.0.0.1.example.invalid/v1",
        "http://127.0.0.1@remote.example.invalid/v1",
        "http://localhost:11434@remote.example.invalid/v1",
        "http://user:password@localhost:11434/v1",
        "http://localhost:invalid/v1",
        "http://localhost:65536/v1",
        "http://[invalid/v1",
        "http://local\nhost:11434/v1",
        "http://localhost:11434/v1?redirect=remote",
        "http://localhost:11434/v1#remote",
        "http://ollama:11434/v1",
    ],
)
def test_local_provider_rejects_invalid_or_nonlocal_endpoint(url: str) -> None:
    configured = Settings(
        **(
            settings_kwargs()
            | {
                "model_provider": "local_openai_compatible",
                "model_id": "local-test-model",
                "model_base_url": url,
                "model_cost_ceiling_usd": 0,
            }
        )
    )

    assert "local MODEL_BASE_URL" in " ".join(configured.validate_runtime())


@pytest.mark.parametrize("url", ["http://localhost:11434/v1", "http://127.0.0.1:8080/v1"])
def test_local_provider_accepts_exact_loopback_endpoints(url: str) -> None:
    configured = Settings(
        **(
            settings_kwargs()
            | {
                "model_provider": "local_openai_compatible",
                "model_id": "local-test-model",
                "model_base_url": url,
                "model_cost_ceiling_usd": 0,
            }
        )
    )

    assert configured.validate_runtime() == []


def test_model_constructor_rejects_nonlocal_endpoint_before_client_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from incidentgraph import investigator

    def unexpected_client(**kwargs: object) -> None:
        pytest.fail("invalid local endpoint must be rejected before client creation")

    monkeypatch.setattr(investigator, "ChatOpenAI", unexpected_client)
    configured = Settings(
        **(
            settings_kwargs()
            | {
                "model_provider": "local_openai_compatible",
                "model_id": "local-test-model",
                "model_base_url": "http://localhost.example.invalid/v1",
                "model_cost_ceiling_usd": 0,
            }
        )
    )

    with pytest.raises(ValueError, match="local MODEL_BASE_URL"):
        investigator.OpenAIInvestigatorModel(configured)


def test_principal_requires_explicit_service_scope() -> None:
    values = settings_kwargs()
    values["auth_tokens_json"] = json.dumps(
        {
            hash_token("unscoped-token"): {
                "principal_id": "viewer-1",
                "roles": ["viewer"],
            }
        }
    )
    settings = Settings(**values)

    assert "must declare at least one SERVICE_ID" in " ".join(settings.validate_runtime())
