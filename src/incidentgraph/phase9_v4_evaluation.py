"""Phase 9 v4 workflow integration for the repair-3 trusted bounded policy.

Frozen v1/v2/v3 evaluators remain immutable historical evidence. This module supplies the new
workflow boundary only; it does not define or open a fresh held-out dataset.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Mapping, Sequence
from typing import Any, Protocol
from uuid import UUID, uuid4

from incidentgraph.config import Settings
from incidentgraph.investigation_tools import CaptureToolbox
from incidentgraph.investigator import ModelResult, ModelUsage, ToolName, ToolResult
from incidentgraph.models import EvidenceItem, InvestigationReport, ReportOutcome
from incidentgraph.phase9_evaluation import _canonical
from incidentgraph.phase9_repair import (
    POLICY_VERSION,
    build_policy_evidence,
    evidence_packet,
    render_report,
    resolve_policy_decision,
)
from incidentgraph.phase9_v2_evaluation import (
    BundleName,
    ObservationPlan,
    _bundle_requests,
    _execute_requests,
    _initial_requests,
    _resolve,
    _runtime_context,
)
from incidentgraph.phase9_v3_dataset import CAPTURE_ROOT as V3_CAPTURE_ROOT
from incidentgraph.phase9_v4_dataset import CAPTURE_ROOT as V4_CAPTURE_ROOT

WORKFLOW_VERSION = "phase9-v4-repair3-workflow-v1"


class BundlePlanner(Protocol):
    async def plan(self, context: str) -> ModelResult: ...


class ReplayEvaluationToolbox(CaptureToolbox):
    """Replay captured telemetry while making document retrieval explicitly unavailable.

    Retrieval quality was already frozen and evaluated separately. Both compared v4 workflows
    receive the same bounded unavailability result, so it cannot change their relative access.
    """

    def _retrieve(self, tool: ToolName, value: Any, context: Any) -> ToolResult:
        del value, context
        return ToolResult(
            tool=tool,
            status="error",
            summary="document retrieval is outside the post-repair agent regression",
            error_code="UNAVAILABLE",
        )


def _default_toolbox(settings: Settings, case: Mapping[str, Any]) -> CaptureToolbox:
    capture_root = (
        V4_CAPTURE_ROOT if str(case["case_id"]).startswith("incident-v4-") else V3_CAPTURE_ROOT
    )
    return ReplayEvaluationToolbox(settings, capture_root)


def _trace_sha256(outcomes: Sequence[ToolResult]) -> str:
    payload = [item.model_dump(mode="json") for item in outcomes]
    return hashlib.sha256(_canonical(payload).encode()).hexdigest()


def _planner_context(case: Mapping[str, Any], remaining: Sequence[BundleName]) -> str:
    return json.dumps(
        {
            "question": case["question"],
            "target_service": case["target_service"],
            "remaining_observation_bundles": list(remaining),
            "constraint": (
                "Choose which bounded bundle to collect first. Trusted code always collects both."
            ),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


async def _collect_initial(
    case: dict[str, Any], toolbox: CaptureToolbox, investigation_id: UUID
) -> tuple[list[ToolResult], str, float]:
    context = _runtime_context(case, investigation_id)
    resolved, latency = await _resolve(case, toolbox, context)
    outcomes = [resolved]
    if resolved.status != "ok":
        return outcomes, "", latency
    service_id = str(resolved.data["service_id"])
    initial, elapsed = await _execute_requests(
        toolbox, _initial_requests(case, service_id), context
    )
    return [*outcomes, *initial], service_id, latency + elapsed


async def _collect_bundle(
    case: dict[str, Any],
    toolbox: CaptureToolbox,
    investigation_id: UUID,
    bundle: BundleName,
) -> tuple[list[ToolResult], float]:
    return await _execute_requests(
        toolbox,
        _bundle_requests(case, bundle),
        _runtime_context(case, investigation_id),
    )


def _finalize_policy_report(
    *,
    case: dict[str, Any],
    workflow: str,
    outcomes: Sequence[ToolResult],
    source_job_id: str,
    usage: ModelUsage,
    model_calls: int,
    tool_latency_ms: float,
    active_duration_ms: float,
) -> tuple[InvestigationReport, EvidenceItem, list[str]]:
    packet = evidence_packet(outcomes)
    source_trace_sha256 = _trace_sha256(outcomes)
    policy_evidence = build_policy_evidence(
        packet,
        case,
        source_job_id=source_job_id,
        source_trace_sha256=source_trace_sha256,
    )
    resolution = resolve_policy_decision(packet, policy_evidence)
    raw_evidence = [item for outcome in outcomes for item in outcome.evidence]
    report = render_report(
        case,
        resolution.decision,
        packet,
        [*raw_evidence, policy_evidence],
        selected_fact_refs=resolution.selected_fact_refs,
        source_job_id=source_job_id,
        source_trace_sha256=source_trace_sha256,
        model_calls=model_calls,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        model_latency_ms=usage.latency_ms,
        tool_calls=len(outcomes),
        tool_latency_ms=tool_latency_ms,
        active_duration_ms=active_duration_ms,
    )
    report = report.model_copy(
        update={
            "termination_reason": "phase9_v4_trusted_policy_complete",
            "trace_reference": (
                f"evaluation://{WORKFLOW_VERSION}/{workflow}/{source_job_id}"
                f"?trace_sha256={source_trace_sha256}"
            ),
        }
    )
    return report, policy_evidence, resolution.selected_fact_refs


def _run_payload(
    *,
    case: Mapping[str, Any],
    workflow: str,
    outcomes: Sequence[ToolResult],
    report: InvestigationReport | None,
    policy_evidence: EvidenceItem | None,
    selected_fact_refs: Sequence[str],
    errors: Sequence[str],
    decision_summaries: Sequence[str],
    usage: ModelUsage,
    model_calls: int,
    tool_latency_ms: float,
    started: float,
) -> dict[str, Any]:
    evidence = [item for outcome in outcomes for item in outcome.evidence]
    if policy_evidence is not None:
        evidence.append(policy_evidence)
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
        "workflow": workflow,
        "workflow_version": WORKFLOW_VERSION,
        "policy_version": POLICY_VERSION,
        "status": status,
        "report_valid": valid,
        "termination_reason": (
            "phase9_v4_trusted_policy_complete" if valid else "phase9_v4_trusted_policy_failed"
        ),
        "error_summaries": list(errors),
        "evidence_ids": [str(item.evidence_id) for item in evidence],
        "derived_policy_evidence": (
            policy_evidence.model_dump(mode="json") if policy_evidence is not None else None
        ),
        "selected_fact_refs": list(selected_fact_refs),
        "tool_trace": [item.model_dump(mode="json") for item in outcomes],
        "decision_summaries": list(decision_summaries),
        "counters": {
            "model_calls": model_calls,
            "tool_calls": len(outcomes),
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "estimated_cost_usd": 0,
            "model_latency_ms": usage.latency_ms,
            "tool_latency_ms": tool_latency_ms,
            "active_duration_ms": (time.perf_counter() - started) * 1_000,
        },
        "report": report.model_dump(mode="json") if report is not None else None,
    }


async def run_fixed_case(
    case: dict[str, Any],
    settings: Settings,
    *,
    source_job_id: str | None = None,
    toolbox: CaptureToolbox | None = None,
) -> dict[str, Any]:
    """Collect the complete fixed observation set and finalize with trusted policy code."""

    started = time.perf_counter()
    investigation_id = uuid4()
    toolbox = toolbox or _default_toolbox(settings, case)
    outcomes, service_id, tool_latency = await _collect_initial(case, toolbox, investigation_id)
    errors: list[str] = []
    report: InvestigationReport | None = None
    policy_evidence: EvidenceItem | None = None
    selected_refs: list[str] = []
    if not service_id:
        errors.append(outcomes[0].summary)
    else:
        requests = [
            *_bundle_requests(case, "resource_signals"),
            *_bundle_requests(case, "context_signals"),
        ]
        observed, elapsed = await _execute_requests(
            toolbox, requests, _runtime_context(case, investigation_id)
        )
        outcomes.extend(observed)
        tool_latency += elapsed
        try:
            report, policy_evidence, selected_refs = _finalize_policy_report(
                case=case,
                workflow="fixed",
                outcomes=outcomes,
                source_job_id=source_job_id or f"v4-fixed-{case['case_id']}",
                usage=ModelUsage(),
                model_calls=0,
                tool_latency_ms=tool_latency,
                active_duration_ms=(time.perf_counter() - started) * 1_000,
            )
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
    return _run_payload(
        case=case,
        workflow="fixed",
        outcomes=outcomes,
        report=report,
        policy_evidence=policy_evidence,
        selected_fact_refs=selected_refs,
        errors=errors,
        decision_summaries=["Collected the pre-registered complete fixed observation set."],
        usage=ModelUsage(),
        model_calls=0,
        tool_latency_ms=tool_latency,
        started=started,
    )


async def run_adaptive_case(
    case: dict[str, Any],
    settings: Settings,
    planner: BundlePlanner,
    *,
    source_job_id: str | None = None,
    toolbox: CaptureToolbox | None = None,
) -> dict[str, Any]:
    """Let one model call choose bundle order; trusted code forces complete access and diagnosis."""

    started = time.perf_counter()
    investigation_id = uuid4()
    toolbox = toolbox or _default_toolbox(settings, case)
    outcomes, service_id, tool_latency = await _collect_initial(case, toolbox, investigation_id)
    errors: list[str] = []
    decision_summaries: list[str] = []
    usage = ModelUsage()
    model_calls = 0
    report: InvestigationReport | None = None
    policy_evidence: EvidenceItem | None = None
    selected_refs: list[str] = []
    if not service_id:
        errors.append(outcomes[0].summary)
    else:
        remaining: list[BundleName] = ["resource_signals", "context_signals"]
        first: BundleName = remaining[0]
        try:
            generated = await planner.plan(_planner_context(case, remaining))
            model_calls = 1
            usage = generated.usage
            plan = ObservationPlan.model_validate(generated.value)
            if plan.action == "observe" and plan.bundle in remaining:
                first = plan.bundle
                decision_summaries.append(plan.decision_summary)
            else:
                decision_summaries.append(
                    "Early finish rejected; trusted completeness barrier selected resource signals."
                )
        except Exception as exc:
            model_calls = 1
            decision_summaries.append(
                f"Planner {type(exc).__name__}; trusted fallback selected resource signals first."
            )
        order = [first, *[bundle for bundle in remaining if bundle != first]]
        for bundle in order:
            observed, elapsed = await _collect_bundle(case, toolbox, investigation_id, bundle)
            outcomes.extend(observed)
            tool_latency += elapsed
        decision_summaries.append(
            "Trusted completeness barrier collected both bounded observation bundles."
        )
        try:
            report, policy_evidence, selected_refs = _finalize_policy_report(
                case=case,
                workflow="adaptive",
                outcomes=outcomes,
                source_job_id=source_job_id or f"v4-adaptive-{case['case_id']}",
                usage=usage,
                model_calls=model_calls,
                tool_latency_ms=tool_latency,
                active_duration_ms=(time.perf_counter() - started) * 1_000,
            )
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
    return _run_payload(
        case=case,
        workflow="adaptive",
        outcomes=outcomes,
        report=report,
        policy_evidence=policy_evidence,
        selected_fact_refs=selected_refs,
        errors=errors,
        decision_summaries=decision_summaries,
        usage=usage,
        model_calls=model_calls,
        tool_latency_ms=tool_latency,
        started=started,
    )
