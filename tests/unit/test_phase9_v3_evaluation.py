from __future__ import annotations

from incidentgraph.phase9_v3_evaluation import (
    RawDiagnosisDecision,
    RawObservationPlan,
    agent_jobs,
    derive_signal_summary,
    normalize_diagnosis,
    normalize_plan,
)


def _metric(source: str, maximum: float, **labels: str) -> dict[str, object]:
    return {
        "template_source": source,
        "maximum": maximum,
        "metric": labels,
    }


def _payload(*summaries: dict[str, object], changes: int = 0) -> dict[str, object]:
    observations: list[dict[str, object]] = [
        {
            "status": "ok",
            "error_code": None,
            "data": {"series_summaries": list(summaries)},
        }
    ]
    if changes:
        observations.append(
            {
                "status": "ok",
                "error_code": None,
                "data": {"change_count": changes},
            }
        )
    return {"observations": observations}


def test_v3_normalizes_harmless_plan_cross_field_mismatch() -> None:
    normalized = normalize_plan(
        RawObservationPlan(
            action="finish",
            bundle="resource_signals",
            decision_summary="Enough evidence is available.",
        ),
        ["resource_signals", "context_signals"],
    )

    assert normalized.action == "finish"
    assert normalized.bundle is None


def test_ordinary_cache_misses_do_not_become_a_cache_fault() -> None:
    summary = derive_signal_summary(
        _payload(
            _metric("cache_outcomes", 5.5, service="payments", result="hit"),
            _metric("cache_outcomes", 1.25, service="payments", result="miss"),
        )
    )

    assert "cache_degradation" not in summary["active_signals"]
    assert summary["bounded_healthy_candidate"] is True


def test_dominant_cache_misses_are_an_explicit_unit_aware_signal() -> None:
    summary = derive_signal_summary(
        _payload(
            _metric("cache_outcomes", 2.0, service="payments", result="hit"),
            _metric("cache_outcomes", 6.0, service="payments", result="miss"),
        )
    )

    assert summary["active_signals"] == ["cache_degradation"]
    assert summary["bounded_healthy_candidate"] is False


def test_competing_change_and_latency_signals_force_honest_abstention() -> None:
    summary = derive_signal_summary(
        _payload(
            _metric(
                "dependency_outcomes",
                1.0,
                service="checkout",
                dependency="payments",
                outcome="error",
            ),
            _metric(
                "request_latency_p95",
                0.24,
                service="payments",
                route="/pay",
            ),
            changes=1,
        )
    )

    assert summary["active_signals"] == ["deployment_regression", "downstream_latency"]
    assert summary["ambiguous"] is True


def test_checkout_only_latency_with_a_change_is_not_false_ambiguity() -> None:
    summary = derive_signal_summary(
        _payload(
            _metric(
                "dependency_outcomes",
                1.0,
                service="checkout",
                dependency="payments",
                outcome="error",
            ),
            _metric(
                "request_latency_p95",
                0.24,
                service="checkout",
                route="/checkout",
            ),
            _metric(
                "request_latency_p95",
                0.01,
                service="payments",
                route="/pay",
            ),
            changes=1,
        )
    )

    assert summary["active_signals"] == ["deployment_regression"]
    assert summary["ambiguous"] is False


def test_missing_telemetry_overrides_incoherent_no_incident_output() -> None:
    signal_summary = derive_signal_summary(
        {
            "observations": [
                {
                    "status": "error",
                    "error_code": "INSUFFICIENT_DATA",
                    "data": {
                        "service_id": "svc-payments",
                        "template": "request_latency",
                    },
                }
            ]
        }
    )
    raw = RawDiagnosisDecision(
        outcome="no_incident_detected",
        component="svc-payments",
        mechanism="cache_degradation",
        explanation="The raw model mixed incompatible fields.",
    )

    normalized = normalize_diagnosis(raw, signal_summary)

    assert normalized.outcome == "inconclusive"
    assert normalized.component == "none"
    assert normalized.mechanism == "insufficient_observation"
    assert normalized.limitation


def test_probable_cause_without_a_bounded_signal_is_not_a_false_incident() -> None:
    raw = RawDiagnosisDecision(
        outcome="probable_cause",
        component="svc-payments",
        mechanism="cache_degradation",
        explanation="A nonzero cache miss value was treated as causal.",
    )

    normalized = normalize_diagnosis(raw, derive_signal_summary(_payload()))

    assert normalized.outcome == "no_incident_detected"
    assert normalized.component == "none"
    assert normalized.mechanism == "healthy"


def test_fresh_run_plan_has_120_unique_budgeted_jobs() -> None:
    jobs = agent_jobs()

    assert len(jobs) == 120
    assert len({item["job_id"] for item in jobs}) == 120
    assert sum(item["split"] == "dev" for item in jobs) == 60
    assert sum(item["split"] == "heldout" for item in jobs) == 60
