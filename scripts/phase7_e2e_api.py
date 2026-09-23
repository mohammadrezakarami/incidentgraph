"""Run the real local API with explicit browser-test identities and no model calls."""

from __future__ import annotations

import json
import os
from pathlib import Path

import uvicorn

from incidentgraph.api import create_app
from incidentgraph.auth import hash_token
from incidentgraph.config import Settings

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)


def main() -> None:
    tokens = {
        hash_token("phase7-e2e-owner-token"): {
            "principal_id": "phase7-e2e-owner",
            "roles": ["viewer", "reviewer"],
            "service_ids": ["svc-gateway", "svc-checkout", "svc-payments"],
        },
        hash_token("phase7-e2e-other-token"): {
            "principal_id": "phase7-e2e-other",
            "roles": ["viewer", "reviewer"],
            "service_ids": ["svc-gateway", "svc-checkout", "svc-payments"],
        },
    }
    settings = Settings(  # type: ignore[call-arg]
        environment="test",
        auth_tokens_json=json.dumps(tokens),
        frontend_origin="http://127.0.0.1:5173",
        model_provider="local_openai_compatible",
        model_id="phase7-browser-fixture-never-invoked",
        model_base_url="http://127.0.0.1:11434/v1",
        model_cost_ceiling_usd=0,
    )
    uvicorn.run(create_app(settings), host="127.0.0.1", port=8000, log_level="warning")


if __name__ == "__main__":
    main()
