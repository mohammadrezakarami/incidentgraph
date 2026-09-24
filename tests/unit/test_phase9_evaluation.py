from incidentgraph.phase9_evaluation import (
    DEV_REPEAT_CASE_IDS,
    _aggregate_agent,
    _normalize_label,
    agent_jobs,
    score_incident_run,
)


def _run(report: dict[str, object] | None) -> dict[str, object]:
    return {
        "case_id": "incident-heldout-001",
        "workflow": "adaptive",
        "split": "heldout",
        "repeat": 1,
        "group_id": "capture-1",
        "report_valid": report is not None,
        "status": "completed" if report is not None else "failed",
        "evidence_ids": ["evidence-1"],
        "error_summaries": [],
        "counters": {
            "model_calls": 2,
            "tool_calls": 3,
            "input_tokens": 10,
            "output_tokens": 5,
            "estimated_cost_usd": 0,
            "active_duration_ms": 1_000,
        },
        "report": report,
    }


def test_frozen_job_plan_has_required_comparisons() -> None:
    jobs = agent_jobs()

    assert len(DEV_REPEAT_CASE_IDS) == 10
    assert len(jobs) == 120
    assert sum(job["split"] == "dev" for job in jobs) == 60
    assert sum(job["split"] == "heldout" for job in jobs) == 60
    assert {job["workflow"] for job in jobs} == {"fixed", "adaptive"}
    assert len({job["job_id"] for job in jobs}) == 120


def test_scoring_requires_component_and_mechanism_in_same_hypothesis() -> None:
    report = {
        "outcome": "probable_cause",
        "limitations": [],
        "ranked_hypotheses": [
            {
                "rank": 1,
                "suspected_component": "Payments",
                "mechanism": "downstream latency",
                "supporting_evidence_ids": ["evidence-1"],
                "contradicting_evidence_ids": [],
            }
        ],
        "observed_symptoms": [],
        "observed_impact": [],
        "potential_impact": [],
        "recommended_next_steps": [],
    }
    label = {
        "case_type": "identifiable",
        "accepted_components": ["payments"],
        "accepted_mechanisms": ["downstream_latency"],
    }

    score = score_incident_run(_run(report), label)

    assert score["top1_correct"] is True
    assert score["top3_correct"] is True
    assert score["all_citations_valid"] is True
    assert _normalize_label("Database-Pool / Exhaustion") == "database_pool_exhaustion"
    assert _normalize_label("svc-payments") == "payments"


def test_abstention_false_incident_and_aggregate_denominators() -> None:
    inconclusive = {
        "outcome": "inconclusive",
        "limitations": ["independent discriminator unavailable"],
        "ranked_hypotheses": [],
        "observed_symptoms": [],
        "observed_impact": [],
        "potential_impact": [],
        "recommended_next_steps": [],
    }
    insufficient = score_incident_run(
        _run(inconclusive),
        {
            "case_type": "insufficient",
            "accepted_components": [],
            "accepted_mechanisms": ["insufficient_observation"],
        },
    )
    probable = {**inconclusive, "outcome": "probable_cause"}
    healthy = score_incident_run(
        _run(probable),
        {
            "case_type": "healthy",
            "accepted_components": [],
            "accepted_mechanisms": ["healthy"],
        },
    )

    aggregate = _aggregate_agent([insufficient, healthy])

    assert insufficient["appropriate_abstention"] is True
    assert healthy["false_incident"] is True
    assert aggregate["appropriate_abstention"]["denominator"] == 1
    assert aggregate["false_incidents"]["denominator"] == 1
    assert aggregate["usage"]["estimated_cost_usd"] == 0
