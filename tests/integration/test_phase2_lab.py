from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import httpx
import pytest

from incidentgraph.capture_verification import verify_capture_suite
from incidentgraph.lab_cli import LabOperatorSettings

pytestmark = [pytest.mark.integration, pytest.mark.lab_integration]


@pytest.mark.skipif(
    os.getenv("RUN_LAB_INTEGRATION") != "1",
    reason="Phase 2 lab integration is not enabled",
)
async def test_real_transaction_metrics_and_control_boundary() -> None:
    settings = LabOperatorSettings()  # type: ignore[call-arg]
    order_id = f"ord-integration-{uuid4().hex[:12]}"
    async with httpx.AsyncClient(timeout=5) as client:
        transaction = await client.post(
            f"{settings.lab_gateway_url}/checkout",
            headers={"X-Request-ID": f"req-{uuid4().hex}"},
            json={
                "order_id": order_id,
                "amount_cents": 1_500,
                "payment_token": "tok_test_1",
            },
        )
        assert transaction.status_code == 200
        assert transaction.json()["status"] == "approved"
        assert transaction.headers["X-Trace-ID"]

        unauthorized = await client.post(
            f"{settings.lab_payments_url}/__control/fault",
            json={
                "kind": "latency",
                "duration_seconds": 5,
                "delay_ms": 10,
            },
        )
        assert unauthorized.status_code == 401

        await asyncio.sleep(1.2)
        prometheus = await client.get(
            f"{settings.prometheus_url}/api/v1/query",
            params={"query": "sum by (service) (lab_http_requests_total)"},
        )
        prometheus.raise_for_status()
        services = {result["metric"]["service"] for result in prometheus.json()["data"]["result"]}
        assert services == {"gateway", "checkout", "payments"}


@pytest.mark.skipif(
    os.getenv("RUN_LAB_INTEGRATION") != "1",
    reason="Phase 2 lab integration is not enabled",
)
def test_live_capture_suite_contract() -> None:
    settings = LabOperatorSettings()  # type: ignore[call-arg]
    result = verify_capture_suite(
        settings.lab_capture_dir,
        settings.lab_evaluator_labels,
    )

    assert result.independent_fault_capture_count >= 12
    assert result.control_capture_count >= 5
    assert result.hash_manifests_valid
    assert result.telemetry_signals_valid
    assert result.trace_continuity_valid
    assert result.evaluator_separation_valid
    assert result.recovery_valid
