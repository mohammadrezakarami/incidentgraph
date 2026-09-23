from __future__ import annotations

import pytest

from incidentgraph.durability import (
    ResumePayloadError,
    authenticated_review_resume,
    versioned_follow_up,
)


def test_authenticated_review_resume_uses_only_stored_reference() -> None:
    command = authenticated_review_resume(
        {
            "task_kind": "review_revision",
            "input_payload": {
                "review_id": "review-123",
                "decision": "request_revision",
                "rationale": "Collect another bounded signal.",
            },
        }
    )

    assert command.resume == {
        "decision": "request_revision",
        "decision_reference": "postgres://incidentgraph_app/review_requests/review-123",
    }


def test_follow_up_requires_explicit_version_and_budget() -> None:
    command = versioned_follow_up(
        {
            "task_kind": "follow_up",
            "target_report_version": 2,
            "input_payload": {"question": "Does the new metric change the conclusion?"},
            "budget": {"max_model_calls": 2, "max_tool_calls": 3},
            "cumulative_usage": {"model_calls": 5, "tool_calls": 4},
        }
    )

    assert command.goto == "plan_next_observation"
    assert command.update["report_version"] == 2
    assert command.update["revision_model_calls_start"] == 5
    assert command.update["revision_max_model_calls"] == 2


def test_resume_rejects_untrusted_or_incomplete_payloads() -> None:
    with pytest.raises(ResumePayloadError):
        authenticated_review_resume(
            {"task_kind": "review_resume", "input_payload": {"decision": "accept"}}
        )
    with pytest.raises(ResumePayloadError):
        versioned_follow_up(
            {
                "task_kind": "follow_up",
                "target_report_version": 2,
                "input_payload": {"question": "Follow up safely?"},
                "budget": {},
            }
        )
