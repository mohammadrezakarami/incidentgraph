from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest

from incidentgraph.investigator import (
    ModelResult,
    ModelUsage,
    ToolResult,
    validate_report_citations,
)
from incidentgraph.phase9_repair import (
    MODEL,
    MODEL_DIGEST,
    ROOT,
    Selection,
    build_observation_workflow,
    development_records,
    evidence_packet,
    probe,
    prompt_packet,
    render_report,
    validate_selection,
)
from incidentgraph.phase9_v2_evaluation import ObservationPlan


@pytest.fixture
def dev() -> dict[str, Any]:
    return {r["case_id"].rsplit("-", 1)[1]: r for r in development_records()}


def packet(record: dict[str, Any]) -> dict[str, Any]:
    return evidence_packet([ToolResult.model_validate(t) for t in record["tool_trace"]])


@pytest.mark.parametrize(
    "case,signal",
    [
        ("001", "downstream_latency"),
        ("004", "database_pool_exhaustion"),
        ("007", "dependency_errors"),
        ("010", "cache_degradation"),
        ("013", "deployment_regression"),
        ("016", "cpu_contention"),
        ("019", "dependency_errors"),
    ],
)
def test_known_development_faults_keep_their_numeric_provenance(
    dev: dict[str, Any],
    case: str,
    signal: str,
) -> None:
    p = packet(dev[case])
    assert p["signal_summary"]["active_signals"] == [signal]
    assert not p["signal_summary"]["telemetry_gaps"]
    refs = p["candidate_fact_refs"][signal]
    assert refs
    raw = Selection(
        outcome="probable_cause",
        mechanism=signal,
        component="svc-checkout" if case in {"004", "013"} else "svc-payments",
        supporting_refs=refs,
        explanation="Synthetic test: selected measured lab signal.",
    )
    decision = validate_selection(raw, p)
    assert set(map(str, decision.supporting_evidence_ids)).issubset(dev[case]["evidence_ids"])
    assert len(prompt_packet(p)) < 4000
    assert "evidence_id" not in prompt_packet(p)


@pytest.mark.parametrize("case", ["026", "029"])
def test_missing_or_competing_evidence_cannot_become_a_healthy_report(
    dev: dict[str, Any],
    case: str,
) -> None:
    p = packet(dev[case])
    assert p["signal_summary"]["telemetry_gaps"] or p["signal_summary"]["ambiguous"]
    with pytest.raises(ValueError, match="inconclusive"):
        validate_selection(
            Selection(
                outcome="no_incident_detected",
                component="none",
                mechanism="healthy",
                supporting_refs=["F1"],
                explanation="No incident found.",
            ),
            p,
        )


def test_healthy_development_case_retains_citable_measurements(dev: dict[str, Any]) -> None:
    r = dev["021"]
    p = packet(r)
    assert p["signal_summary"]["bounded_healthy_candidate"]
    decision = validate_selection(
        Selection(
            outcome="no_incident_detected",
            component="none",
            mechanism="healthy",
            supporting_refs=["F1", "F2"],
            explanation="No measured lab threshold was crossed.",
        ),
        p,
    )
    cases = {
        c["case_id"]: c
        for c in map(
            json.loads, (ROOT / "data/evaluation/incident-cases-v3.jsonl").read_text().splitlines()
        )
    }
    evidence = [e for t in r["tool_trace"] for e in ToolResult.model_validate(t).evidence]
    report = render_report(cases[r["case_id"]], decision, p, evidence)
    assert report.observed_symptoms
    assert validate_report_citations(report, evidence) == []


def test_early_adaptive_stop_exposes_missing_change_observation(dev: dict[str, Any]) -> None:
    r = dev["013"]
    partial = [
        ToolResult.model_validate(t) for t in r["tool_trace"] if t["tool"] != "get_recent_changes"
    ]
    p = evidence_packet(partial)
    assert "approved_change_observation" in p["signal_summary"]["telemetry_gaps"]
    assert not p["signal_summary"]["bounded_healthy_candidate"]


@pytest.mark.parametrize("refs", [["F999"], ["F1", "F1"], []])
def test_invalid_or_empty_citations_are_rejected(dev: dict[str, Any], refs: list[str]) -> None:
    with pytest.raises(ValueError):
        validate_selection(
            Selection(
                outcome="probable_cause",
                component="svc-payments",
                mechanism="cpu_contention",
                supporting_refs=refs,
                explanation="CPU fault.",
            ),
            packet(dev["016"]),
        )


def test_fault_is_not_silently_normalized_to_healthy(dev: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="contradicts"):
        validate_selection(
            Selection(
                outcome="no_incident_detected",
                component="none",
                mechanism="healthy",
                supporting_refs=["F1"],
                explanation="The model ignored abnormal telemetry.",
            ),
            packet(dev["001"]),
        )


async def test_probe_offline_never_contacts_a_model(tmp_path: Path, monkeypatch: Any) -> None:
    async def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("offline audit attempted a network request")

    monkeypatch.setattr(httpx.AsyncClient, "get", forbidden)
    monkeypatch.setattr(httpx.AsyncClient, "post", forbidden)
    result = await probe(tmp_path, offline=True)
    assert result["model_calls"] == 0
    assert result["cases"] == 10
    records = json.loads((tmp_path / "records.json").read_text())
    assert all("-dev-" in r["case_id"] for r in records)


async def test_adaptive_workflow_collects_changes_even_when_model_finishes_early(
    dev: dict[str, Any],
) -> None:
    r = dev["013"]
    cases = {
        c["case_id"]: c
        for c in map(
            json.loads, (ROOT / "data/evaluation/incident-cases-v3.jsonl").read_text().splitlines()
        )
    }

    class SavedToolbox:
        async def execute(self, request: Any, context: Any) -> ToolResult:
            for t in r["tool_trace"]:
                if t["tool"] != request.tool.value:
                    continue
                if t["tool"] == "get_metrics" and (
                    t["data"].get("service_id") != request.arguments["service_id"]
                    or t["data"].get("template") != request.arguments["template"]
                ):
                    continue
                return ToolResult.model_validate(t)
            raise AssertionError("unexpected tool request")

    async def early_finish(context: str) -> ModelResult:
        return ModelResult(
            ObservationPlan(
                action="finish",
                bundle=None,
                decision_summary="Model prematurely considers evidence sufficient.",
            ),
            ModelUsage(),
        )

    graph = build_observation_workflow(SavedToolbox(), early_finish)
    state = await graph.ainvoke({"case": cases[r["case_id"]], "investigation_id": str(uuid4())})
    assert len(state["outcomes"]) == 14
    assert state["plan_calls"] == 2
    assert len(state["corrections"]) == 2
    assert evidence_packet(state["outcomes"])["signal_summary"]["active_signals"] == [
        "deployment_regression"
    ]


async def test_probe_keeps_raw_failures_and_caps_retries(tmp_path: Path, monkeypatch: Any) -> None:
    real_client = httpx.AsyncClient
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        assert request.url.host == "127.0.0.1"
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": MODEL, "digest": MODEL_DIGEST}]})
        calls += 1
        body = json.loads(request.content)
        assert body["options"]["num_ctx"] == 8192
        assert "accepted_mechanisms" not in json.dumps(body)
        return httpx.Response(200, json={"message": {"content": "not valid JSON"}})

    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kw: real_client(**kw, transport=httpx.MockTransport(respond))
    )
    result = await probe(tmp_path)
    assert calls == 20
    assert result["correct"] == 0
    records = json.loads((tmp_path / "records.json").read_text())
    assert all(len(r["attempts"]) == 2 and "error" in r["attempts"][0] for r in records)
