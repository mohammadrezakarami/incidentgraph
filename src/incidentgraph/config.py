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

    model_provider: Literal["disabled", "openai", "local_openai_compatible"] = "disabled"
    model_id: str = ""
    model_api_key: SecretStr | None = None
    model_base_url: str | None = None
    model_max_calls: int = Field(default=10, ge=1, le=20)
    model_token_budget: int = Field(default=20_000, ge=1_000, le=200_000)
    model_max_output_tokens: int = Field(default=1_200, ge=128, le=8_000)
    model_timeout_seconds: int = Field(default=45, ge=5, le=120)
    model_cost_ceiling_usd: float = Field(default=0, ge=0, le=100)
    model_input_cost_per_million_usd: float = Field(default=0, ge=0, le=100)
    model_output_cost_per_million_usd: float = Field(default=0, ge=0, le=500)
    investigator_max_tool_calls: int = Field(default=16, ge=1, le=32)
    investigator_max_rounds: int = Field(default=6, ge=1, le=12)
    investigator_tool_timeout_seconds: int = Field(default=10, ge=1, le=30)
    investigator_deadline_seconds: int = Field(default=180, ge=30, le=600)

    embedding_model_id: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_model_revision: str = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
    embedding_dimension: int = Field(default=384, ge=1, le=4096)
    embedding_device: Literal["cpu"] = "cpu"
    embedding_batch_size: int = Field(default=16, ge=1, le=64)
    corpus_id: str = Field(default="incidentgraph-lab-corpus-v1", min_length=1, max_length=128)

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
        if self.model_provider == "openai":
            if self.model_api_key is None or not self.model_api_key.get_secret_value():
                problems.append("MODEL_API_KEY is required for the OpenAI provider")
            if self.model_cost_ceiling_usd <= 0:
                problems.append(
                    "MODEL_COST_CEILING_USD must be positive when a provider is enabled"
                )
            if self.model_input_cost_per_million_usd <= 0:
                problems.append("MODEL_INPUT_COST_PER_MILLION_USD must be explicitly configured")
            if self.model_output_cost_per_million_usd <= 0:
                problems.append("MODEL_OUTPUT_COST_PER_MILLION_USD must be explicitly configured")
        if self.model_provider == "local_openai_compatible":
            if not self.model_base_url:
                problems.append("MODEL_BASE_URL is required for a local model provider")
            elif not self.model_base_url.startswith(("http://127.0.0.1", "http://localhost")):
                problems.append("local MODEL_BASE_URL must use a loopback address")
            if self.model_cost_ceiling_usd != 0:
                problems.append("local model runs must keep MODEL_COST_CEILING_USD at zero")
        if len(self.embedding_model_revision) != 40 or any(
            char not in "0123456789abcdef" for char in self.embedding_model_revision
        ):
            problems.append("EMBEDDING_MODEL_REVISION must be a full lowercase Git commit SHA")
        if self.embedding_model_id == "sentence-transformers/all-MiniLM-L6-v2":
            if self.embedding_dimension != 384:
                problems.append("all-MiniLM-L6-v2 requires EMBEDDING_DIMENSION=384")
        return problems
