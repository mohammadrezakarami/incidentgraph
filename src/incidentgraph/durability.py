from __future__ import annotations

import asyncio
from typing import Any, Protocol

from langgraph.types import Command

from incidentgraph.models import InvestigationReport, JobLease
from incidentgraph.persistence import Database


class ResumePayloadError(ValueError):
    pass


class DurableWorkflow(Protocol):
    async def ainvoke(self, value: Any, config: dict[str, Any]) -> dict[str, Any]: ...


class DurableWorkflowCoordinator:
    """Join the durable queue lease to one PostgreSQL-checkpointed graph attempt."""

    def __init__(
        self,
        database: Database,
        workflow: DurableWorkflow,
        *,
        require_review: bool,
        review_ttl_seconds: int,
        lease_seconds: int = 30,
    ) -> None:
        self.database = database
        self.workflow = workflow
        self.require_review = require_review
        self.review_ttl_seconds = review_ttl_seconds
        self.lease_seconds = lease_seconds

    async def process(
        self,
        lease: JobLease,
        *,
        initial_input: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if await self.database.acknowledge_cancellation(lease):
            return {"status": "cancelled"}
        context = await self.database.get_execution_context(lease)
        config = {"configurable": {"thread_id": str(context["thread_id"])}}
        if lease.task_kind in {"review_resume", "review_revision"}:
            workflow_input: Any = authenticated_review_resume(context)
        elif lease.task_kind == "follow_up":
            workflow_input = versioned_follow_up(context)
        else:
            if initial_input is None:
                raise ResumePayloadError("initial investigation input is required")
            workflow_input = {**initial_input, "thread_id": str(context["thread_id"])}

        result = await self._invoke_with_lease(lease, workflow_input, config)
        if result is None:
            return {"status": "cancelled"}
        if await self.database.acknowledge_cancellation(lease):
            return {**result, "status": "cancelled"}
        if lease.task_kind == "review_resume":
            status = await self.database.complete_review_resume(lease)
            return {**result, "status": status.value}

        raw_report = result.get("report")
        if raw_report is None:
            raise ResumePayloadError("workflow attempt returned no publishable report")
        report = InvestigationReport.model_validate(raw_report)
        evidence_summary: list[dict[str, Any]] = []
        uncertainties: list[str] = list(report.limitations)
        interrupted = result.get("__interrupt__")
        waiting_for_review = bool(interrupted)
        if self.require_review and not waiting_for_review:
            raise ResumePayloadError("review-required workflow completed without an interrupt")
        if waiting_for_review:
            if not isinstance(interrupted, (list, tuple)) or not interrupted:
                raise ResumePayloadError("review interrupt collection is invalid")
            payload = interrupted[0].value
            if not isinstance(payload, dict):
                raise ResumePayloadError("review interrupt payload is invalid")
            evidence = payload.get("evidence_summary", [])
            missing = payload.get("uncertainties", [])
            if isinstance(evidence, list):
                evidence_summary = [item for item in evidence if isinstance(item, dict)]
            if isinstance(missing, list):
                uncertainties = [str(item) for item in missing]
        publication = await self.database.publish_report_under_lease(
            lease,
            report,
            publication_key=f"workflow-report-v{report.report_version}",
            require_review=waiting_for_review,
            review_ttl_seconds=self.review_ttl_seconds,
            evidence_summary=evidence_summary,
            uncertainties=uncertainties,
        )
        return {**result, "durable_publication": publication.model_dump(mode="json")}

    async def _invoke_with_lease(
        self,
        lease: JobLease,
        workflow_input: Any,
        config: dict[str, Any],
    ) -> dict[str, Any] | None:
        task = asyncio.create_task(self.workflow.ainvoke(workflow_input, config=config))
        interval = max(1.0, min(5.0, self.lease_seconds / 3))
        try:
            while not task.done():
                done, _ = await asyncio.wait({task}, timeout=interval)
                if done:
                    break
                if await self.database.cancellation_requested(lease):
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                    await self.database.acknowledge_cancellation(lease)
                    return None
                await self.database.heartbeat(lease, self.lease_seconds)
            return await task
        except BaseException:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            raise


def authenticated_review_resume(context: dict[str, Any]) -> Command[str]:
    """Build a LangGraph resume only from lease-fenced, server-stored review input."""
    task_kind = context.get("task_kind")
    if task_kind not in {"review_resume", "review_revision"}:
        raise ResumePayloadError("work item is not a review resume")
    payload = context.get("input_payload")
    if not isinstance(payload, dict):
        raise ResumePayloadError("stored review payload is missing")
    review_id = payload.get("review_id")
    decision = payload.get("decision")
    if not isinstance(review_id, str) or not review_id:
        raise ResumePayloadError("stored review reference is missing")
    if decision not in {"accept", "reject", "request_revision"}:
        raise ResumePayloadError("stored review decision is invalid")
    return Command(
        resume={
            "decision": decision,
            "decision_reference": f"postgres://incidentgraph_app/review_requests/{review_id}",
        }
    )


def versioned_follow_up(context: dict[str, Any]) -> Command[str]:
    """Continue a completed thread with the explicit stored question and version budget."""
    if context.get("task_kind") != "follow_up":
        raise ResumePayloadError("work item is not a follow-up")
    payload = context.get("input_payload")
    budget = context.get("budget")
    target = context.get("target_report_version")
    if not isinstance(payload, dict) or not isinstance(payload.get("question"), str):
        raise ResumePayloadError("stored follow-up question is missing")
    if not isinstance(budget, dict) or not budget:
        raise ResumePayloadError("stored follow-up budget is missing")
    if not isinstance(target, int) or target < 2:
        raise ResumePayloadError("stored follow-up report version is invalid")
    usage = context.get("cumulative_usage")
    if not isinstance(usage, dict):
        raise ResumePayloadError("stored cumulative usage is missing")
    model_calls = usage.get("model_calls")
    tool_calls = usage.get("tool_calls")
    max_model_calls = budget.get("max_model_calls")
    max_tool_calls = budget.get("max_tool_calls")
    if not all(
        isinstance(value, int)
        for value in (model_calls, tool_calls, max_model_calls, max_tool_calls)
    ):
        raise ResumePayloadError("stored follow-up counters or limits are invalid")
    return Command(
        update={
            "question": payload["question"],
            "report_version": target,
            "termination_reason": "",
            "report": None,
            "report_valid": False,
            "review_request": None,
            "review_decision_reference": None,
            "revision_model_calls_start": model_calls,
            "revision_tool_calls_start": tool_calls,
            "revision_max_model_calls": max_model_calls,
            "revision_max_tool_calls": max_tool_calls,
        },
        goto="plan_next_observation",
    )
