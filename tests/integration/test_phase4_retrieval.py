from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

from incidentgraph.config import Settings
from incidentgraph.retrieval import Neo4jRetriever, RetrievalError, RetrievalRequest

pytestmark = [pytest.mark.integration, pytest.mark.retrieval_integration]


def request(variant: str, *, service: str = "gateway") -> RetrievalRequest:
    return RetrievalRequest(
        question=(
            "Gateway latency rose while cache hits fell. Which downstream service "
            "and cache runbook should be investigated?"
        ),
        target_service=service,
        environment="lab",
        cutoff=datetime(2026, 9, 23, 12, tzinfo=UTC),
        authorized_service_ids=("svc-gateway", "svc-checkout", "svc-payments"),
        variant=variant,
    )


@pytest.mark.skipif(
    os.getenv("RUN_RETRIEVAL_INTEGRATION") != "1",
    reason="Phase 4 retrieval integration is not enabled",
)
def test_three_retrievers_share_contract_and_graph_recovers_downstream_evidence() -> None:
    settings = Settings()  # type: ignore[call-arg]
    with Neo4jRetriever(settings) as retriever:
        vector = retriever.retrieve(request("vector"))
        hybrid = retriever.retrieve(request("hybrid"))
        graph = retriever.retrieve(request("graph"))
        alias = retriever.retrieve(request("vector", service="edge"))

    results = (vector, hybrid, graph)
    assert len({item.corpus_version for item in results}) == 1
    assert len({item.embedding_revision for item in results}) == 1
    assert all(len(item.selected_candidates) <= 8 for item in results)
    assert all(item.selected_token_count <= 5_000 for item in results)
    assert alias.resolved_target_service_id == "svc-gateway"
    assert all(
        candidate.trust_status in {"trusted", "reviewed", "reference"}
        for result in results
        for candidate in result.selected_candidates
    )
    assert all(
        candidate.valid_from <= datetime(2026, 9, 23, 12, tzinfo=UTC)
        and (
            candidate.valid_to is None or datetime(2026, 9, 23, 12, tzinfo=UTC) < candidate.valid_to
        )
        for result in results
        for candidate in result.selected_candidates
    )

    required = {"doc-payments-cache-contract", "runbook-cache"}
    assert not required.intersection(item.source_id for item in vector.selected_candidates[:5])
    assert not required.intersection(item.source_id for item in hybrid.selected_candidates[:5])
    graph_hits = [item for item in graph.selected_candidates[:5] if item.source_id in required]
    assert graph_hits
    assert any(item.graph_path and item.graph_path.hops > 0 for item in graph_hits)
    assert any("path=" in item.provenance_reference for item in graph.evidence)


@pytest.mark.skipif(
    os.getenv("RUN_RETRIEVAL_INTEGRATION") != "1",
    reason="Phase 4 retrieval integration is not enabled",
)
def test_retrieval_enforces_authorization_before_search() -> None:
    settings = Settings()  # type: ignore[call-arg]
    denied = request("graph").model_copy(
        update={"authorized_service_ids": ("svc-checkout", "svc-payments")}
    )
    with (
        Neo4jRetriever(settings) as retriever,
        pytest.raises(RetrievalError, match="outside authorization"),
    ):
        retriever.retrieve(denied)
