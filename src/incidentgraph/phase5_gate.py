from __future__ import annotations

import asyncio
import json
import platform
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from pydantic import SecretStr

from incidentgraph.config import Settings
from incidentgraph.incident_evaluation import CASE_PATH, verify_fixture
from incidentgraph.investigation_tools import CaptureToolbox
from incidentgraph.investigator import (
    OpenAIInvestigatorModel,
    initial_state,
    persistent_workflow,
)
from incidentgraph.models import InvestigationCreate, InvestigationMode, InvestigationReport
from incidentgraph.persistence import Database

MODEL_ID = "qwen3:4b-instruct-2507-q4_K_M"
MODEL_BASE_URL = "http://127.0.0.1:11434/v1"
OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"
CASE_IDS = ("incident-dev-001", "incident-dev-009")
ARTIFACT = (
    Path(__file__).resolve().parents[2]
    / "artifacts"
    / "evaluation"
    / "phase5-real-local"
    / "gate-results.json"
)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _model_settings(base: Settings) -> Settings:
    return base.model_copy(
        update={
            "environment": "local",
            "auth_tokens_json": json.dumps(
                {
                    "0" * 64: {
                        "principal_id": "phase5-local-gate",
                        "roles": ["viewer"],
                        "service_ids": ["svc-gateway", "svc-checkout", "svc-payments"],
                    }
                }
            ),
            "model_provider": "local_openai_compatible",
            "model_id": MODEL_ID,
            "model_api_key": SecretStr("ollama-local-ignored"),
            "model_base_url": MODEL_BASE_URL,
            "model_max_calls": 10,
            "model_token_budget": 30_000,
            "model_max_output_tokens": 600,
            "model_timeout_seconds": 240,
            "model_cost_ceiling_usd": 0.0,
            "model_input_cost_per_million_usd": 0.0,
            "model_output_cost_per_million_usd": 0.0,
            "investigator_max_tool_calls": 12,
            "investigator_max_rounds": 4,
            "investigator_tool_timeout_seconds": 10,
            "investigator_deadline_seconds": 900,
        }
    )


async def _runtime_identity() -> tuple[dict[str, Any], str]:
    async with httpx.AsyncClient(timeout=10) as client:
        tags_response = await client.get(OLLAMA_TAGS_URL)
        tags_response.raise_for_status()
        version_response = await client.get("http://127.0.0.1:11434/api/version")
        version_response.raise_for_status()
    models = tags_response.json().get("models", [])
    match = next((item for item in models if item.get("name") == MODEL_ID), None)
    if match is None:
        raise RuntimeError(f"required local model is not installed: {MODEL_ID}")
    return (
        {
            "name": match.get("name"),
            "digest": match.get("digest"),
            "size": match.get("size"),
            "details": match.get("details"),
        },
        str(version_response.json().get("version", "unknown")),
    )


async def _run_case(
    case: dict[str, Any], settings: Settings, model: OpenAIInvestigatorModel
) -> dict[str, Any]:
    request_id = uuid4()
    request = InvestigationCreate(
        question=case["question"],
        target_service=case["target_service"],
        environment="lab",
        window_start=datetime.fromisoformat(case["window_start"]),
        window_end=datetime.fromisoformat(case["window_end"]),
        mode=InvestigationMode.REPLAY,
    )
    database = Database(settings.app_database_dsn.get_secret_value())
    await database.open()
    try:
        accepted = await database.create_investigation(
            owner_id="phase5-local-gate",
            request_id=request_id,
            idempotency_key=f"{case['case_id']}-{request_id}",
            request=request,
        )
    finally:
        await database.close()

    state = initial_state(
        investigation_id=accepted.investigation_id,
        request_id=request_id,
        principal_id="phase5-local-gate",
        authorized_service_ids=("svc-gateway", "svc-checkout", "svc-payments"),
        question=request.question,
        target_service=request.target_service,
        window_start=request.window_start,
        window_end=request.window_end,
        observation_cutoff=datetime.fromisoformat(case["observation_cutoff"]),
        mode=request.mode,
        snapshot_id=case["snapshot_id"],
        corpus_version=settings.corpus_id,
    )
    config: dict[str, Any] = {"configurable": {"thread_id": state["thread_id"]}}
    toolbox = CaptureToolbox(settings)
    async with persistent_workflow(settings, model, toolbox, setup=True) as workflow:
        result = await workflow.ainvoke(state, config=config)
        saved = await workflow.aget_state(config)

    report = (
        InvestigationReport.model_validate(result["report"]).model_dump(mode="json")
        if result.get("report")
        else None
    )
    tool_trace = [
        {
            "tool": item["tool"],
            "status": item["status"],
            "summary": item["summary"],
            "data": item["data"],
            "evidence_ids": [evidence["evidence_id"] for evidence in item["evidence"]],
        }
        for item in result.get("tool_outcomes", [])
    ]
    tool_sequence = [
        item["tool"]
        for item in result.get("tool_outcomes", [])
        if item["tool"] not in {"resolve_service", "get_service_context"}
    ]
    return {
        "case_id": case["case_id"],
        "snapshot_id": case["snapshot_id"],
        "target_service": case["target_service"],
        "status": result.get("status"),
        "report_valid": result.get("report_valid", False),
        "termination_reason": result.get("termination_reason"),
        "tool_sequence": tool_sequence,
        "tool_trace": tool_trace,
        "decision_summaries": result.get("decision_summaries", []),
        "error_summaries": result.get("error_summaries", []),
        "evidence_ids": [item["evidence_id"] for item in result.get("evidence", [])],
        "counters": result.get("counters", {}),
        "checkpoint_status": saved.values.get("status"),
        "report": report,
    }


def _assess(runs: list[dict[str, Any]]) -> dict[str, Any]:
    sequences = [run["tool_sequence"] for run in runs]
    second_tools = [sequence[1] if len(sequence) > 1 else None for sequence in sequences]
    checks = {
        "two_real_cases": len(runs) == 2,
        "valid_grounded_reports": all(run["report_valid"] for run in runs),
        "real_model_calls_recorded": all(run["counters"].get("model_calls", 0) > 0 for run in runs),
        "real_tools_executed": all(len(sequence) >= 2 for sequence in sequences),
        "grounded_observation_recorded": all(run["evidence_ids"] for run in runs),
        "different_evidence_driven_next_tools": (
            all(tool is not None for tool in second_tools) and len(set(second_tools)) == 2
        ),
        "zero_monetary_cost": all(run["counters"].get("estimated_cost_usd") == 0 for run in runs),
        "persistent_completion": all(
            run["checkpoint_status"] in {"completed", "inconclusive"} for run in runs
        ),
    }
    return {"status": "pass" if all(checks.values()) else "fail", "checks": checks}


async def run_gate() -> dict[str, Any]:
    if ARTIFACT.exists():
        previous = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        if previous.get("gate", {}).get("status") != "pass":
            attempts = sorted(ARTIFACT.parent.glob("gate-attempt-*.json"))
            attempt_path = ARTIFACT.parent / f"gate-attempt-{len(attempts) + 1:02d}.json"
            attempt_path.write_text(
                json.dumps(previous, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
    seal_before = verify_fixture()
    base = Settings()  # type: ignore[call-arg]
    settings = _model_settings(base)
    problems = settings.validate_runtime()
    if problems:
        raise ValueError("invalid local gate configuration: " + "; ".join(problems))
    model_identity, ollama_version = await _runtime_identity()
    cases_by_id = {item["case_id"]: item for item in _jsonl(CASE_PATH)}
    selected = [cases_by_id[case_id] for case_id in CASE_IDS]
    model = OpenAIInvestigatorModel(settings)
    runs = [await _run_case(case, settings, model) for case in selected]
    seal_after = verify_fixture()
    if seal_before["digest"] != seal_after["digest"]:
        raise RuntimeError("held-out seal changed during the real-model gate")
    artifact = {
        "schema_version": 1,
        "run_kind": "phase5-free-local-real-model-gate",
        "created_at": datetime.now().astimezone().isoformat(),
        "provider": "local_openai_compatible",
        "paid_calls": False,
        "model": model_identity,
        "runtime": {
            "ollama": ollama_version,
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "limits": {
            "model_calls": settings.model_max_calls,
            "token_budget": settings.model_token_budget,
            "tool_calls": settings.investigator_max_tool_calls,
            "rounds": settings.investigator_max_rounds,
            "deadline_seconds": settings.investigator_deadline_seconds,
        },
        "heldout_seal_before": seal_before,
        "heldout_seal_after": seal_after,
        "runs": runs,
        "gate": _assess(runs),
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifact


def main() -> None:
    artifact = asyncio.run(run_gate())
    print(json.dumps(artifact, indent=2, sort_keys=True))
    raise SystemExit(0 if artifact["gate"]["status"] == "pass" else 2)


if __name__ == "__main__":
    main()
