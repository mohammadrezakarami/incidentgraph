"""Run the real local API with explicit browser-test identities and no model calls."""

from __future__ import annotations

import json
import os
import tempfile
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
    with tempfile.TemporaryDirectory(prefix="incidentgraph-browser-captures-") as temporary:
        capture_root = Path(temporary)
        capture = capture_root / "cap-browser-test-00000001"
        capture.mkdir()
        (capture / "manifest.json").write_text(
            json.dumps(
                {
                    "observation_start": "2026-09-23T12:00:00Z",
                    "observation_cutoff": "2026-09-23T12:05:00Z",
                    "services": ["gateway", "checkout", "payments"],
                    "provenance_category": "browser_test_fixture",
                    "limitations": ["Deterministic browser fixture; no model validation."],
                }
            ),
            encoding="utf-8",
        )
        uvicorn.run(
            create_app(settings, capture_root=capture_root),
            host="127.0.0.1",
            port=8000,
            log_level="warning",
        )


if __name__ == "__main__":
    main()
