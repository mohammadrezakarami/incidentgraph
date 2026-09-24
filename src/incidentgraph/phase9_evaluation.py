from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import math
import platform
import shutil
import subprocess
import time
from collections import Counter
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
from pydantic import SecretStr

from incidentgraph.config import Settings
from incidentgraph.incident_evaluation import (
    CASE_PATH,
    verify_fixture,
)
from incidentgraph.incident_evaluation import (
    LABEL_PATH as INCIDENT_LABEL_PATH,
)
from incidentgraph.incident_evaluation import (
    SEAL_PATH as INCIDENT_SEAL_PATH,
)
from incidentgraph.ingestion import MANIFEST_PATH, ROOT, TOPOLOGY_PATH
from incidentgraph.investigation_tools import CaptureToolbox
from incidentgraph.investigator import (
    PROMPT_VERSION,
    SYSTEM_POLICY,
    TOOL_CATALOG,
    WORKFLOW_VERSION,
    OpenAIInvestigatorModel,
    ReportDraft,
    ToolName,
    ToolRequest,
    ToolRuntimeContext,
    build_workflow,
    initial_state,
    validate_report_citations,
)
from incidentgraph.models import (
    EvidenceItem,
    IncidentWindow,
    InvestigationMode,
    InvestigationReport,
    ReportOutcome,
    ReviewStatus,
    UsageAndTiming,
)
from incidentgraph.retrieval import (
    LABEL_PATH as RETRIEVAL_LABEL_PATH,
)
from incidentgraph.retrieval import (
    QUESTION_PATH,
    EvaluationLabel,
    EvaluationQuestion,
    Neo4jRetriever,
    RetrievalRequest,
    RetrievalVariant,
    retrieval_metrics,
    verify_heldout_seal,
)
from incidentgraph.retrieval import (
    SEAL_PATH as RETRIEVAL_SEAL_PATH,
)

FREEZE_PATH = ROOT / "config" / "phase9-freeze-v1.json"
DEFAULT_RUN_DIR = ROOT / "artifacts" / "evaluation" / "phase9-frozen-v1"
MODEL_ID = "qwen3:4b-instruct-2507-q4_K_M"
MODEL_BASE_URL = "http://127.0.0.1:11434/v1"
OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"
AUTHORIZED_SERVICES = ("svc-gateway", "svc-checkout", "svc-payments")
DEV_REPEAT_CASE_IDS = (
    "incident-dev-001",
    "incident-dev-005",
    "incident-dev-009",
    "incident-dev-012",
    "incident-dev-015",
    "incident-dev-018",
    "incident-dev-021",
    "incident-dev-023",
    "incident-dev-026",
    "incident-dev-028",
)
WORKFLOWS = ("fixed", "adaptive")
SCORING_VERSION = "phase9-scoring-v1"
RUN_PLAN_VERSION = "phase9-zero-paid-colab-v1"


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_revision() -> str:
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is required for frozen evaluation provenance")
    result = subprocess.run(  # noqa: S603 - resolved executable with fixed arguments
        [git, "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def frozen_paths() -> tuple[Path, ...]:
    return (
        CASE_PATH,
        INCIDENT_LABEL_PATH,
        INCIDENT_SEAL_PATH,
        QUESTION_PATH,
        RETRIEVAL_LABEL_PATH,
        RETRIEVAL_SEAL_PATH,
        MANIFEST_PATH,
        ROOT / "data" / "corpus" / "documents.json",
        TOPOLOGY_PATH,
        ROOT / "pyproject.toml",
        ROOT / "uv.lock",
        ROOT / "src" / "incidentgraph" / "investigator.py",
        ROOT / "src" / "incidentgraph" / "retrieval.py",
        ROOT / "src" / "incidentgraph" / "phase9_evaluation.py",
    )


def freeze_document() -> dict[str, Any]:
    incident_seal = verify_fixture()
    retrieval_seal = verify_heldout_seal()
    return {
        "schema_version": 1,
        "freeze_id": "phase9-frozen-v1",
        "state": "frozen-before-heldout-evaluation",
        "frozen_at": "2026-09-24T00:00:00Z",
        "git_revision": _git_revision(),
        "sealed_inputs": {
            "incident": incident_seal,
            "retrieval": retrieval_seal,
        },
        "file_sha256": {str(path.relative_to(ROOT)): _sha256(path) for path in frozen_paths()},
        "prompts": {
            "prompt_version": PROMPT_VERSION,
            "workflow_version": WORKFLOW_VERSION,
            "system_policy_sha256": hashlib.sha256(SYSTEM_POLICY.encode()).hexdigest(),
            "tool_catalog_sha256": hashlib.sha256(TOOL_CATALOG.encode()).hexdigest(),
        },
        "model": {
            "provider": "local_openai_compatible",
            "requested_id": MODEL_ID,
            "expected_digest": ("0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0"),
            "temperature": 0,
            "max_calls_per_case": 10,
            "token_budget_per_case": 30_000,
            "max_output_tokens": 600,
            "timeout_seconds": 240,
            "active_deadline_seconds": 900,
            "monetary_cost_ceiling_usd": 0,
        },
        "embedding": {
            "model": "sentence-transformers/all-MiniLM-L6-v2",
            "revision": "1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
            "dimension": 384,
            "device": "cpu",
        },
        "retrieval": {
            "variants": [item.value for item in RetrievalVariant],
            "split": "heldout",
            "questions": 20,
            "runs_per_question": 1,
            "corpus_snapshot": "incidentgraph-lab-corpus-v1-466b7569b585",
            "context_chunks": 8,
            "context_tokens": 5_000,
        },
        "agent_comparison": {
            "workflows": list(WORKFLOWS),
            "fixed_rules": [
                "target error-rate metric",
                "target request-latency metric",
                "captured dependency graph to depth two",
                "target logs without severity preselection",
                "approved changes in the immutable window",
                "graph-enhanced runbook retrieval at the immutable cutoff",
            ],
            "dev_repeat_case_ids": list(DEV_REPEAT_CASE_IDS),
            "dev_repeats": 3,
            "heldout_cases": 30,
            "heldout_repeats": 1,
            "maximum_agent_jobs": 120,
            "execution": "free Colab T4, resumable shards; never paid",
        },
        "scoring": {
            "version": SCORING_VERSION,
            "component_and_mechanism_match": "casefolded exact label after separator normalization",
            "top1": "rank-one hypothesis matches an accepted component and mechanism",
            "top3": "any of at most three hypotheses matches both labels",
            "appropriate_abstention": "inconclusive outcome with at least one limitation",
            "false_incident": "probable_cause outcome on a healthy case",
            "citation_validity": "each cited UUID resolves to evidence collected in that run",
            "supported_claims": "manual rubric over deterministic sample of at least 20 reports",
            "uncertainty_unit": "independent capture group, not paraphrase or repeat",
        },
        "targets": {
            "retrieval_recall_at_5": 0.80,
            "diagnosis_top1": 0.75,
            "diagnosis_top3": 0.90,
            "appropriate_abstention_minimum": "4/5",
            "false_incident_maximum": "1/5",
            "citation_validity": 1.0,
            "supported_claim_rate": 0.95,
            "policy_violations": 0,
            "warm_p95_active_seconds": 90,
            "coverage": 0.85,
        },
        "known_pre_run_limitation": {
            "code": "INCIDENT_CAPTURE_PREDATES_FINAL_CORPUS",
            "capture_cutoff_latest": "2026-09-22T21:48:44.837164+00:00",
            "corpus_majority_valid_from": "2026-09-23T00:00:00Z",
            "effect": (
                "most runbooks are correctly ineligible for incident-case retrieval; seals and "
                "timestamps will not be rewritten after the fact"
            ),
        },
        "paid_calls_authorized": False,
        "run_plan_version": RUN_PLAN_VERSION,
    }


def verify_freeze(path: Path = FREEZE_PATH) -> dict[str, Any]:
    frozen = json.loads(path.read_text(encoding="utf-8"))
    mismatches: list[dict[str, str]] = []
    for relative, expected in frozen["file_sha256"].items():
        actual = _sha256(ROOT / relative)
        if actual != expected:
            mismatches.append({"path": relative, "expected": expected, "actual": actual})
    incident = verify_fixture()
    retrieval = verify_heldout_seal()
    if incident["digest"] != frozen["sealed_inputs"]["incident"]["digest"]:
        mismatches.append({"path": "incident seal", "expected": "frozen", "actual": "changed"})
    if retrieval["digest"] != frozen["sealed_inputs"]["retrieval"]["digest"]:
        mismatches.append({"path": "retrieval seal", "expected": "frozen", "actual": "changed"})
    if mismatches:
        raise ValueError(f"Phase 9 freeze verification failed: {mismatches}")
    return {
        "status": "pass",
        "freeze_id": frozen["freeze_id"],
        "file_count": len(frozen["file_sha256"]),
        "incident_seal": incident["digest"],
        "retrieval_seal": retrieval["digest"],
    }


def _model_settings(base: Settings) -> Settings:
    return base.model_copy(
        update={
            "environment": "local",
            "auth_tokens_json": json.dumps(
                {
                    "0" * 64: {
                        "principal_id": "phase9-evaluator",
                        "roles": ["viewer"],
                        "service_ids": list(AUTHORIZED_SERVICES),
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
            "human_review_required": False,
        }
    )


async def runtime_identity() -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10) as client:
        tags = (await client.get(OLLAMA_TAGS_URL)).raise_for_status().json()
        version = (await client.get("http://127.0.0.1:11434/api/version")).raise_for_status().json()
    match = next((item for item in tags.get("models", []) if item.get("name") == MODEL_ID), None)
    if match is None:
        raise RuntimeError(f"required local model is not installed: {MODEL_ID}")
    expected = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))["model"]["expected_digest"]
    if match.get("digest") != expected:
        raise RuntimeError(
            f"model digest mismatch: expected {expected}, received {match.get('digest')}"
        )
    return {
        "name": match.get("name"),
        "digest": match.get("digest"),
        "size": match.get("size"),
        "details": match.get("details"),
        "ollama_version": version.get("version"),
    }


def _runtime_context(case: dict[str, Any], investigation_id: UUID) -> ToolRuntimeContext:
    return ToolRuntimeContext(
        investigation_id=investigation_id,
        principal_id="phase9-evaluator",
        authorized_service_ids=AUTHORIZED_SERVICES,
        environment="lab",
        window_start=datetime.fromisoformat(case["window_start"]),
        window_end=datetime.fromisoformat(case["window_end"]),
        observation_cutoff=datetime.fromisoformat(case["observation_cutoff"]),
        snapshot_id=case["snapshot_id"],
    )


def _fixed_requests(case: dict[str, Any], service_id: str) -> list[ToolRequest]:
    common_window = {
        "window_start": case["window_start"],
        "window_end": case["window_end"],
    }
    return [
        ToolRequest(
            tool=ToolName.GET_METRICS,
            arguments={
                "service_id": service_id,
                "template": "error_rate",
                **common_window,
                "resolution_seconds": 1,
            },
            reason="Fixed rule 1: inspect target error rate.",
        ),
        ToolRequest(
            tool=ToolName.GET_METRICS,
            arguments={
                "service_id": service_id,
                "template": "request_latency",
                **common_window,
                "resolution_seconds": 1,
            },
            reason="Fixed rule 2: inspect target request latency.",
        ),
        ToolRequest(
            tool=ToolName.GET_DEPENDENCIES,
            arguments={
                "service_id": service_id,
                "direction": "both",
                "depth": 2,
                "observation_time": case["observation_cutoff"],
            },
            reason="Fixed rule 3: inspect the bounded captured dependency graph.",
        ),
        ToolRequest(
            tool=ToolName.SEARCH_LOGS,
            arguments={"service_ids": [service_id], **common_window, "limit": 50},
            reason="Fixed rule 4: inspect target logs without outcome-dependent filters.",
        ),
        ToolRequest(
            tool=ToolName.GET_RECENT_CHANGES,
            arguments={"service_ids": [service_id], **common_window},
            reason="Fixed rule 5: inspect approved changes in the immutable window.",
        ),
        ToolRequest(
            tool=ToolName.RETRIEVE_RUNBOOKS,
            arguments={
                "query": case["question"],
                "service_ids": [service_id],
                "cutoff": case["observation_cutoff"],
                "variant": "graph",
            },
            reason="Fixed rule 6: retrieve graph-enhanced runbook evidence.",
        ),
    ]


async def _run_fixed_case(
    case: dict[str, Any], settings: Settings, model: OpenAIInvestigatorModel
) -> dict[str, Any]:
    investigation_id = uuid4()
    context = _runtime_context(case, investigation_id)
    toolbox = CaptureToolbox(settings)
    resolve = await toolbox.execute(
        ToolRequest(
            tool=ToolName.RESOLVE_SERVICE,
            arguments={"name": case["target_service"], "environment": "lab"},
            reason="Resolve the fixed workflow target.",
        ),
        context,
    )
    if resolve.status != "ok":
        return {
            "case_id": case["case_id"],
            "workflow": "fixed",
            "status": "failed",
            "report_valid": False,
            "termination_reason": "context_resolution_failed",
            "error_summaries": [resolve.summary],
            "evidence_ids": [],
            "tool_trace": [resolve.model_dump(mode="json")],
            "counters": {"model_calls": 0, "tool_calls": 1, "estimated_cost_usd": 0},
            "report": None,
        }
    service_id = str(resolve.data["service_id"])
    outcomes = [resolve]
    evidence: list[EvidenceItem] = []
    tool_latency_ms = 0.0
    started = time.perf_counter()
    for request in _fixed_requests(case, service_id):
        tool_started = time.perf_counter()
        result = await toolbox.execute(request, context)
        tool_latency_ms += (time.perf_counter() - tool_started) * 1_000
        outcomes.append(result)
        evidence.extend(result.evidence)
    prompt_context = _canonical(
        {
            "question": case["question"],
            "target_service": service_id,
            "environment": "lab",
            "window": [case["window_start"], case["window_end"]],
            "observation_cutoff": case["observation_cutoff"],
            "workflow": "fixed predefined observations",
            "evidence": [item.model_dump(mode="json") for item in evidence],
            "tool_outcomes": [item.model_dump(mode="json") for item in outcomes],
        }
    )
    errors: list[str] = []
    report: InvestigationReport | None = None
    usage = None
    try:
        generated = await model.draft_report(prompt_context)
        usage = generated.usage
        draft = ReportDraft.model_validate(generated.value)
        report = InvestigationReport(
            investigation_id=investigation_id,
            report_version=1,
            mode=InvestigationMode.REPLAY,
            snapshot_id=case["snapshot_id"],
            target_service=service_id,
            environment="lab",
            incident_window=IncidentWindow(
                start=datetime.fromisoformat(case["window_start"]),
                end=datetime.fromisoformat(case["window_end"]),
            ),
            observation_cutoff=datetime.fromisoformat(case["observation_cutoff"]),
            **draft.model_dump(),
            review_status=ReviewStatus.NOT_REQUESTED,
            termination_reason="fixed_observation_plan_completed",
            usage_and_timing=UsageAndTiming(
                model_calls=1,
                tool_calls=len(outcomes),
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                estimated_cost_usd=0,
                active_duration_ms=(time.perf_counter() - started) * 1_000,
                model_latency_ms=usage.latency_ms,
                tool_latency_ms=tool_latency_ms,
                cost_is_estimate=False,
            ),
            trace_reference=f"evaluation://phase9/fixed/{investigation_id}",
        )
        errors.extend(validate_report_citations(report, evidence))
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    valid = report is not None and not errors
    status = (
        "inconclusive"
        if valid and report is not None and report.outcome == ReportOutcome.INCONCLUSIVE
        else "completed"
        if valid
        else "failed"
    )
    return {
        "case_id": case["case_id"],
        "workflow": "fixed",
        "status": status,
        "report_valid": valid,
        "termination_reason": "fixed_observation_plan_completed" if valid else "report_failed",
        "error_summaries": errors,
        "evidence_ids": [str(item.evidence_id) for item in evidence],
        "tool_trace": [item.model_dump(mode="json") for item in outcomes],
        "counters": {
            "model_calls": 1 if usage is not None else 0,
            "tool_calls": len(outcomes),
            "input_tokens": usage.input_tokens if usage is not None else 0,
            "output_tokens": usage.output_tokens if usage is not None else 0,
            "estimated_cost_usd": 0,
            "model_latency_ms": usage.latency_ms if usage is not None else 0,
            "tool_latency_ms": tool_latency_ms,
            "active_duration_ms": (time.perf_counter() - started) * 1_000,
        },
        "report": report.model_dump(mode="json") if report is not None else None,
    }


async def _run_adaptive_case(
    case: dict[str, Any], settings: Settings, model: OpenAIInvestigatorModel
) -> dict[str, Any]:
    investigation_id = uuid4()
    state = initial_state(
        investigation_id=investigation_id,
        request_id=uuid4(),
        principal_id="phase9-evaluator",
        authorized_service_ids=AUTHORIZED_SERVICES,
        question=case["question"],
        target_service=case["target_service"],
        window_start=datetime.fromisoformat(case["window_start"]),
        window_end=datetime.fromisoformat(case["window_end"]),
        observation_cutoff=datetime.fromisoformat(case["observation_cutoff"]),
        mode=InvestigationMode.REPLAY,
        snapshot_id=case["snapshot_id"],
        corpus_version=settings.corpus_id,
    )
    started = time.perf_counter()
    workflow = build_workflow(settings, model, CaptureToolbox(settings))
    result = await workflow.ainvoke(state, config={"recursion_limit": 64})
    counters = dict(result.get("counters", {}))
    counters["active_duration_ms"] = (time.perf_counter() - started) * 1_000
    return {
        "case_id": case["case_id"],
        "workflow": "adaptive",
        "status": result.get("status"),
        "report_valid": result.get("report_valid", False),
        "termination_reason": result.get("termination_reason"),
        "error_summaries": result.get("error_summaries", []),
        "evidence_ids": [item["evidence_id"] for item in result.get("evidence", [])],
        "tool_trace": result.get("tool_outcomes", []),
        "decision_summaries": result.get("decision_summaries", []),
        "counters": counters,
        "report": result.get("report"),
    }


def agent_jobs() -> list[dict[str, Any]]:
    cases = _jsonl(CASE_PATH)
    by_id = {item["case_id"]: item for item in cases}
    jobs: list[dict[str, Any]] = []
    for repeat in range(1, 4):
        for case_id in DEV_REPEAT_CASE_IDS:
            for workflow in WORKFLOWS:
                jobs.append(
                    {
                        "job_id": f"dev-r{repeat}-{workflow}-{case_id}",
                        "split": "dev",
                        "repeat": repeat,
                        "workflow": workflow,
                        "case": by_id[case_id],
                    }
                )
    for case in cases:
        if case["split"] != "heldout":
            continue
        for workflow in WORKFLOWS:
            jobs.append(
                {
                    "job_id": f"heldout-r1-{workflow}-{case['case_id']}",
                    "split": "heldout",
                    "repeat": 1,
                    "workflow": workflow,
                    "case": case,
                }
            )
    if len(jobs) != 120:
        raise ValueError(f"frozen run plan requires 120 jobs, found {len(jobs)}")
    return jobs


async def run_agent_shard(output_dir: Path, shard_index: int, shard_count: int) -> dict[str, Any]:
    verify_freeze()
    if shard_count < 1 or not 0 <= shard_index < shard_count:
        raise ValueError("shard index must be zero-based and less than shard count")
    identity = await runtime_identity()
    base = Settings()  # type: ignore[call-arg]
    settings = _model_settings(base)
    problems = settings.validate_runtime()
    if problems:
        raise ValueError("invalid Phase 9 runtime: " + "; ".join(problems))
    selected = [job for index, job in enumerate(agent_jobs()) if index % shard_count == shard_index]
    await asyncio.to_thread(output_dir.mkdir, parents=True, exist_ok=True)
    path = output_dir / f"agent-part-{shard_index:02d}-of-{shard_count:02d}.jsonl"
    completed = {item["job_id"] for item in _jsonl(path)} if path.exists() else set()
    model = OpenAIInvestigatorModel(settings)
    run_count = 0
    with path.open("a", encoding="utf-8") as handle:
        for job in selected:
            if job["job_id"] in completed:
                continue
            case = job["case"]
            try:
                result = (
                    await _run_fixed_case(case, settings, model)
                    if job["workflow"] == "fixed"
                    else await _run_adaptive_case(case, settings, model)
                )
            except Exception as exc:
                result = {
                    "case_id": case["case_id"],
                    "workflow": job["workflow"],
                    "status": "failed",
                    "report_valid": False,
                    "termination_reason": "unhandled_evaluation_error",
                    "error_summaries": [f"{type(exc).__name__}: {exc}"],
                    "evidence_ids": [],
                    "tool_trace": [],
                    "counters": {
                        "model_calls": 0,
                        "tool_calls": 0,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "estimated_cost_usd": 0,
                        "active_duration_ms": 0,
                    },
                    "report": None,
                }
            record = {
                "schema_version": 1,
                "freeze_id": "phase9-frozen-v1",
                "run_plan_version": RUN_PLAN_VERSION,
                "job_id": job["job_id"],
                "split": job["split"],
                "repeat": job["repeat"],
                "group_id": case["group_id"],
                "provenance_category": case["provenance_category"],
                "snapshot_id": case["snapshot_id"],
                "model": identity,
                "created_at": datetime.now(UTC).isoformat(),
                **result,
            }
            handle.write(_canonical(record) + "\n")
            handle.flush()
            run_count += 1
            print(
                _canonical(
                    {
                        "job": job["job_id"],
                        "status": result["status"],
                        "model_calls": result["counters"].get("model_calls", 0),
                    }
                ),
                flush=True,
            )
    return {
        "status": "complete",
        "path": str(path),
        "shard_index": shard_index,
        "shard_count": shard_count,
        "assigned": len(selected),
        "newly_run": run_count,
        "total_records": len(_jsonl(path)),
    }


def run_retrieval(output_dir: Path) -> dict[str, Any]:
    freeze = verify_freeze()
    questions = [
        EvaluationQuestion.model_validate(item)
        for item in _jsonl(QUESTION_PATH)
        if item["split"] == "heldout"
    ]
    labels = {
        item["question_id"]: EvaluationLabel.model_validate(item)
        for item in _jsonl(RETRIEVAL_LABEL_PATH)
    }
    settings = Settings()  # type: ignore[call-arg]
    rows: list[dict[str, Any]] = []
    with Neo4jRetriever(settings) as retriever:
        for question in questions:
            for variant in RetrievalVariant:
                result = retriever.retrieve(
                    RetrievalRequest(
                        question=question.question,
                        target_service=question.target_service,
                        environment=question.environment,
                        cutoff=question.cutoff,
                        authorized_service_ids=question.authorized_service_ids,
                        variant=variant,
                    )
                )
                ranked = [item.source_id for item in result.selected_candidates]
                rows.append(
                    {
                        "question_id": question.question_id,
                        "group_id": question.group_id,
                        "variant": variant.value,
                        **retrieval_metrics(ranked, labels[question.question_id].relevance),
                        "top_5_source_ids": ranked[:5],
                        "elapsed_ms": result.elapsed_ms,
                        "selected_token_count": result.selected_token_count,
                        "corpus_version": result.corpus_version,
                    }
                )
    aggregate: dict[str, dict[str, float]] = {}
    for variant in RetrievalVariant:
        matches = [row for row in rows if row["variant"] == variant.value]
        aggregate[variant.value] = {
            metric: sum(float(row[metric]) for row in matches) / len(matches)
            for metric in ("recall_at_5", "mrr_at_5", "ndcg_at_5")
        }
        aggregate[variant.value]["mean_elapsed_ms"] = sum(
            float(row["elapsed_ms"]) for row in matches
        ) / len(matches)
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact = {
        "schema_version": 1,
        "freeze": freeze,
        "split": "heldout",
        "question_count": len(questions),
        "rows": rows,
        "aggregate": aggregate,
        "hardware": {"platform": platform.platform(), "machine": platform.machine()},
        "git_revision": _git_revision(),
        "heldout_seal_after": verify_heldout_seal(),
    }
    path = output_dir / "retrieval-heldout.json"
    path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"status": "complete", "path": str(path), "aggregate": aggregate}


def _normalize_label(value: str) -> str:
    normalized = "_".join(value.casefold().replace("-", " ").replace("/", " ").split())
    return normalized.removeprefix("svc_")


def _report_citations(report: dict[str, Any] | None) -> list[str]:
    if report is None:
        return []
    citations: list[str] = []
    for item in report.get("ranked_hypotheses", []):
        citations.extend(item.get("supporting_evidence_ids", []))
        citations.extend(item.get("contradicting_evidence_ids", []))
    for key in ("observed_symptoms", "observed_impact", "potential_impact"):
        for item in report.get(key, []):
            citations.extend(item.get("evidence_ids", []))
    for item in report.get("recommended_next_steps", []):
        citations.extend(item.get("evidence_ids", []))
    return citations


def score_incident_run(run: dict[str, Any], label: dict[str, Any]) -> dict[str, Any]:
    report = run.get("report")
    hypotheses = report.get("ranked_hypotheses", [])[:3] if report else []
    components = {_normalize_label(value) for value in label["accepted_components"]}
    mechanisms = {_normalize_label(value) for value in label["accepted_mechanisms"]}

    def matches(item: dict[str, Any]) -> bool:
        return (
            _normalize_label(str(item.get("suspected_component", ""))) in components
            and _normalize_label(str(item.get("mechanism", ""))) in mechanisms
        )

    citations = _report_citations(report)
    evidence_ids = set(run.get("evidence_ids", []))
    valid_citations = sum(item in evidence_ids for item in citations)
    outcome = report.get("outcome") if report else None
    return {
        "case_id": run["case_id"],
        "workflow": run["workflow"],
        "split": run["split"],
        "repeat": run["repeat"],
        "group_id": run["group_id"],
        "case_type": label["case_type"],
        "top1_correct": bool(hypotheses and matches(hypotheses[0])),
        "top3_correct": any(matches(item) for item in hypotheses),
        "appropriate_abstention": (
            label["case_type"] == "insufficient"
            and outcome == "inconclusive"
            and bool(report.get("limitations"))
        )
        if report
        else False,
        "false_incident": label["case_type"] == "healthy" and outcome == "probable_cause",
        "citation_count": len(citations),
        "valid_citation_count": valid_citations,
        "all_citations_valid": valid_citations == len(citations),
        "task_complete": bool(
            run.get("report_valid")
            and run.get("status") in {"completed", "inconclusive"}
            and report is not None
        ),
        "policy_violation": any(
            "unauthorized" in str(item).casefold() for item in run.get("error_summaries", [])
        ),
        "outcome": outcome,
        "active_duration_ms": float(run.get("counters", {}).get("active_duration_ms", 0)),
        "model_calls": int(run.get("counters", {}).get("model_calls", 0)),
        "tool_calls": int(run.get("counters", {}).get("tool_calls", 0)),
        "input_tokens": int(run.get("counters", {}).get("input_tokens", 0)),
        "output_tokens": int(run.get("counters", {}).get("output_tokens", 0)),
        "estimated_cost_usd": float(run.get("counters", {}).get("estimated_cost_usd", 0)),
    }


def _ratio(rows: Sequence[dict[str, Any]], key: str) -> dict[str, Any]:
    numerator = sum(bool(row[key]) for row in rows)
    denominator = len(rows)
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": numerator / denominator if denominator else None,
    }


def _percentile(values: Iterable[float], percentile: float) -> float | None:
    ordered = sorted(values)
    if not ordered:
        return None
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _aggregate_agent(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    identifiable = [row for row in rows if row["case_type"] == "identifiable"]
    insufficient = [row for row in rows if row["case_type"] == "insufficient"]
    healthy = [row for row in rows if row["case_type"] == "healthy"]
    citation_count = sum(int(row["citation_count"]) for row in rows)
    valid_citations = sum(int(row["valid_citation_count"]) for row in rows)
    return {
        "cases": len(rows),
        "independent_groups": len({row["group_id"] for row in rows}),
        "top1": _ratio(identifiable, "top1_correct"),
        "top3": _ratio(identifiable, "top3_correct"),
        "appropriate_abstention": _ratio(insufficient, "appropriate_abstention"),
        "false_incidents": {
            "numerator": sum(bool(row["false_incident"]) for row in healthy),
            "denominator": len(healthy),
            "rate": (
                sum(bool(row["false_incident"]) for row in healthy) / len(healthy)
                if healthy
                else None
            ),
        },
        "citation_validity": {
            "numerator": valid_citations,
            "denominator": citation_count,
            "rate": valid_citations / citation_count if citation_count else None,
        },
        "task_completion": _ratio(rows, "task_complete"),
        "policy_violations": sum(bool(row["policy_violation"]) for row in rows),
        "p95_active_duration_ms": _percentile(
            (float(row["active_duration_ms"]) for row in rows), 0.95
        ),
        "usage": {
            "model_calls": sum(int(row["model_calls"]) for row in rows),
            "tool_calls": sum(int(row["tool_calls"]) for row in rows),
            "input_tokens": sum(int(row["input_tokens"]) for row in rows),
            "output_tokens": sum(int(row["output_tokens"]) for row in rows),
            "estimated_cost_usd": sum(float(row["estimated_cost_usd"]) for row in rows),
        },
        "outcomes": dict(Counter(str(row["outcome"]) for row in rows)),
    }


def _load_agent_parts(output_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(output_dir.glob("agent-part-*.jsonl")):
        rows.extend(_jsonl(path))
    by_job: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row["job_id"] in by_job and _canonical(row) != _canonical(by_job[row["job_id"]]):
            raise ValueError(f"conflicting duplicate agent job: {row['job_id']}")
        by_job[row["job_id"]] = row
    expected = {item["job_id"] for item in agent_jobs()}
    missing = sorted(expected.difference(by_job))
    extra = sorted(set(by_job).difference(expected))
    if missing or extra:
        raise ValueError(
            f"agent artifacts incomplete: {len(missing)} missing and {len(extra)} unexpected"
        )
    return [by_job[job["job_id"]] for job in agent_jobs()]


def finalize(output_dir: Path) -> dict[str, Any]:
    freeze = verify_freeze()
    retrieval = json.loads((output_dir / "retrieval-heldout.json").read_text(encoding="utf-8"))
    runs = _load_agent_parts(output_dir)
    labels = {item["case_id"]: item for item in _jsonl(INCIDENT_LABEL_PATH)}
    scores = [score_incident_run(run, labels[run["case_id"]]) for run in runs]
    heldout = {
        workflow: _aggregate_agent(
            [row for row in scores if row["split"] == "heldout" and row["workflow"] == workflow]
        )
        for workflow in WORKFLOWS
    }
    dev_repeats = {
        workflow: {
            str(repeat): _aggregate_agent(
                [
                    row
                    for row in scores
                    if row["split"] == "dev"
                    and row["workflow"] == workflow
                    and row["repeat"] == repeat
                ]
            )
            for repeat in range(1, 4)
        }
        for workflow in WORKFLOWS
    }
    adaptive = heldout["adaptive"]
    graph_retrieval = retrieval["aggregate"]["graph"]
    targets = {
        "retrieval_recall_at_5": graph_retrieval["recall_at_5"] >= 0.80,
        "diagnosis_top1": (adaptive["top1"]["rate"] or 0) >= 0.75,
        "diagnosis_top3": (adaptive["top3"]["rate"] or 0) >= 0.90,
        "appropriate_abstention": adaptive["appropriate_abstention"]["numerator"] >= 4,
        "false_incidents": adaptive["false_incidents"]["numerator"] <= 1,
        "citation_validity": adaptive["citation_validity"]["rate"] == 1.0,
        "policy_violations": adaptive["policy_violations"] == 0,
        "warm_p95_active_seconds": (
            adaptive["p95_active_duration_ms"] is not None
            and adaptive["p95_active_duration_ms"] < 90_000
        ),
        "supported_claim_rate": None,
        "coverage": False,
    }
    failures = [
        {
            "job_id": run["job_id"],
            "workflow": run["workflow"],
            "case_id": run["case_id"],
            "case_type": score["case_type"],
            "outcome": score["outcome"],
            "errors": run.get("error_summaries", []),
            "top1_correct": score["top1_correct"],
            "top3_correct": score["top3_correct"],
            "task_complete": score["task_complete"],
        }
        for run, score in zip(runs, scores, strict=True)
        if run["split"] == "heldout"
        and (
            not score["task_complete"]
            or (score["case_type"] == "identifiable" and not score["top1_correct"])
            or score["false_incident"]
            or (score["case_type"] == "insufficient" and not score["appropriate_abstention"])
        )
    ]
    result = {
        "schema_version": 1,
        "freeze": freeze,
        "run_plan": {
            "agent_jobs": len(runs),
            "heldout_runs_per_workflow": 30,
            "dev_runs_per_workflow": 30,
            "paid_calls": False,
        },
        "retrieval": {
            "question_count": retrieval["question_count"],
            "aggregate": retrieval["aggregate"],
        },
        "agent": {"heldout": heldout, "dev_repeats": dev_repeats},
        "targets": targets,
        "gate_status": "pending_manual_review",
        "representative_failures": failures[:20],
        "limitations": [
            "Incident captures predate most corpus validity windows, so runbook retrieval is "
            "correctly unavailable for those cases.",
            "Five healthy and five insufficient held-out cases provide weak statistical evidence.",
            "Paraphrases and repeated development runs are not treated as independent samples.",
            "The retained core coverage target was not met before this run.",
            "Supported factual claim rate remains pending until the manual rubric is completed.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "aggregate.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with (output_dir / "per-case.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(scores[0]))
        writer.writeheader()
        writer.writerows(scores)
    _write_manual_review(output_dir, runs, scores)
    _write_summary(output_dir, result)
    return result


def _write_manual_review(
    output_dir: Path, runs: Sequence[dict[str, Any]], scores: Sequence[dict[str, Any]]
) -> None:
    paired = [item for item in zip(runs, scores, strict=True) if item[0]["split"] == "heldout"]
    failures = [
        item for item in paired if not item[1]["task_complete"] or not item[1]["top1_correct"]
    ]
    successes = [item for item in paired if item not in failures]
    sample = (failures[:12] + successes[:8])[:20]
    if len(sample) < 20:
        sample = paired[:20]
    with (output_dir / "manual-review.jsonl").open("w", encoding="utf-8") as handle:
        for run, score in sample:
            handle.write(
                _canonical(
                    {
                        "job_id": run["job_id"],
                        "case_id": run["case_id"],
                        "workflow": run["workflow"],
                        "case_type": score["case_type"],
                        "report": run.get("report"),
                        "tool_trace": run.get("tool_trace", []),
                        "rubric": {
                            "factual_claim_count": None,
                            "supported_factual_claim_count": None,
                            "unsupported_claims": [],
                            "citation_support_notes": "",
                            "reviewer": "",
                            "reviewed_at": "",
                        },
                    }
                )
                + "\n"
            )


def _write_summary(output_dir: Path, result: dict[str, Any]) -> None:
    lines = [
        "# Phase 9 frozen evaluation",
        "",
        "Status: **PENDING MANUAL REVIEW**.",
        "",
        "All automated aggregates are reproduced from per-case records. The supported-claim "
        "target is intentionally not decided until `manual-review.jsonl` has 20 completed rubrics.",
        "",
        "## Held-out agent comparison",
        "",
        "| Workflow | Top 1 | Top 3 | Abstention | False incidents | Task completion |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for workflow, metrics in result["agent"]["heldout"].items():
        lines.append(
            f"| {workflow} | {metrics['top1']['numerator']}/{metrics['top1']['denominator']} | "
            f"{metrics['top3']['numerator']}/{metrics['top3']['denominator']} | "
            f"{metrics['appropriate_abstention']['numerator']}/"
            f"{metrics['appropriate_abstention']['denominator']} | "
            f"{metrics['false_incidents']['numerator']}/"
            f"{metrics['false_incidents']['denominator']} | "
            f"{metrics['task_completion']['numerator']}/"
            f"{metrics['task_completion']['denominator']} |"
        )
    lines.extend(["", "## Automated target status", ""])
    for name, status in result["targets"].items():
        label = "PENDING" if status is None else "PASS" if status else "FAIL"
        lines.append(f"- `{name}`: **{label}**")
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in result["limitations"])
    lines.append("")
    (output_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="IncidentGraph Phase 9 frozen evaluation")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("print-freeze")
    sub.add_parser("verify-freeze")
    retrieval = sub.add_parser("run-retrieval")
    retrieval.add_argument("--output-dir", type=Path, default=DEFAULT_RUN_DIR)
    agent = sub.add_parser("run-agent-shard")
    agent.add_argument("--output-dir", type=Path, default=DEFAULT_RUN_DIR)
    agent.add_argument("--shard-index", type=int, required=True)
    agent.add_argument("--shard-count", type=int, required=True)
    report = sub.add_parser("finalize")
    report.add_argument("--output-dir", type=Path, default=DEFAULT_RUN_DIR)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "print-freeze":
        print(json.dumps(freeze_document(), indent=2, sort_keys=True))
        return
    if args.command == "verify-freeze":
        print(json.dumps(verify_freeze(), indent=2, sort_keys=True))
        return
    if args.command == "run-retrieval":
        print(json.dumps(run_retrieval(args.output_dir), indent=2, sort_keys=True))
        return
    if args.command == "run-agent-shard":
        result = asyncio.run(run_agent_shard(args.output_dir, args.shard_index, args.shard_count))
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    print(json.dumps(finalize(args.output_dir), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
