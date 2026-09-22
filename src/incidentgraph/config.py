from __future__ import annotations

import json
from functools import cached_property
from typing import Literal

from pydantic import BaseModel, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PrincipalConfig(BaseModel):
    principal_id: str = Field(min_length=1, max_length=128)
    roles: frozenset[Literal["viewer", "reviewer", "operator"]]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="INCIDENTGRAPH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["local", "test", "ci"] = "local"
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1024, le=65535)
    frontend_origin: str = "http://127.0.0.1:5173"

    app_database_dsn: SecretStr
    lab_database_dsn: SecretStr
    neo4j_uri: str
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr
    auth_tokens_json: str = "{}"

    worker_id: str = Field(default="local-worker-1", min_length=1, max_length=128)
    worker_lease_seconds: int = Field(default=30, ge=2, le=300)
    event_retention_days: int = Field(default=30, ge=1, le=365)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    model_provider: Literal["disabled", "openai"] = "disabled"
    model_id: str = ""
    model_max_calls: int = Field(default=10, ge=1, le=20)
    model_cost_ceiling_usd: float = Field(default=0, ge=0, le=100)

    @field_validator("api_host")
    @classmethod
    def bind_local_by_default(cls, value: str) -> str:
        if value not in {"127.0.0.1", "localhost"}:
            raise ValueError("the Phase 1 API must bind to loopback")
        return value

    @cached_property
    def auth_tokens(self) -> dict[str, PrincipalConfig]:
        try:
            raw = json.loads(self.auth_tokens_json)
        except json.JSONDecodeError as exc:
            raise ValueError("AUTH_TOKENS_JSON must be valid JSON") from exc
        if not isinstance(raw, dict):
            raise ValueError("AUTH_TOKENS_JSON must be an object keyed by token hash")
        return {key: PrincipalConfig.model_validate(value) for key, value in raw.items()}

    def validate_runtime(self) -> list[str]:
        problems: list[str] = []
        for field_name, secret in (
            ("APP_DATABASE_DSN", self.app_database_dsn),
            ("LAB_DATABASE_DSN", self.lab_database_dsn),
            ("NEO4J_PASSWORD", self.neo4j_password),
        ):
            if "CHANGE_ME" in secret.get_secret_value():
                problems.append(f"{field_name} still contains CHANGE_ME")
        if not self.auth_tokens:
            problems.append("AUTH_TOKENS_JSON contains no principals")
        if self.model_provider != "disabled":
            if not self.model_id:
                problems.append("MODEL_ID is required when a model provider is enabled")
            if self.model_cost_ceiling_usd <= 0:
                problems.append(
                    "MODEL_COST_CEILING_USD must be positive when a provider is enabled"
                )
        return problems
