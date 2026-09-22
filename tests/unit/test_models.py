from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from incidentgraph.models import InvestigationCreate


def test_request_normalizes_utc_window() -> None:
    end = datetime.now(UTC)
    request = InvestigationCreate(
        question="Why did checkout latency increase during this window?",
        target_service="checkout",
        window_start=end - timedelta(minutes=15),
        window_end=end,
        mode="replay",
    )

    assert request.window_start.utcoffset() == timedelta(0)


def test_request_rejects_unbounded_window() -> None:
    end = datetime.now(UTC)

    with pytest.raises(ValidationError, match="60 minutes"):
        InvestigationCreate(
            question="Why did checkout latency increase during this window?",
            target_service="checkout",
            window_start=end - timedelta(hours=2),
            window_end=end,
            mode="replay",
        )


def test_request_rejects_unbounded_service_identifier() -> None:
    end = datetime.now(UTC)

    with pytest.raises(ValidationError):
        InvestigationCreate(
            question="Why did checkout latency increase during this window?",
            target_service="checkout; MATCH (n) DETACH DELETE n",
            window_start=end - timedelta(minutes=5),
            window_end=end,
            mode="replay",
        )
