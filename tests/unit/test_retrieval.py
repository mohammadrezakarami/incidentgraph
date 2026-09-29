from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from incidentgraph.retrieval import (
    GraphPath,
    Neo4jRetriever,
    RetrievalCandidate,
    RetrievalError,
    RetrievalRequest,
    RetrievalVariant,
    heldout_digest,
    reciprocal_rank_fusion,
    retrieval_metrics,
    sanitize_fulltext_query,
    select_context,
    verify_heldout_seal,
)


def candidate(source_id: str, *, tokens: int = 100, score: float = 0.5) -> RetrievalCandidate:
    now = datetime(2026, 9, 23, tzinfo=UTC)
    return RetrievalCandidate(
        chunk_id=f"chunk-{source_id}",
        source_id=source_id,
        source_version="1.0.0",
        title=source_id,
        section="Overview",
        text=f"Evidence for {source_id}",
        token_count=tokens,
        content_hash=(source_id.encode().hex() + "0" * 64)[:64],
        service_ids=("svc-gateway",),
        observed_at=now,
        valid_from=now,
        valid_to=None,
        trust_status="trusted",
        vector_score=score,
        graph_path=GraphPath(node_ids=("svc-gateway",), relationships=(), hops=0),
    )


def test_fulltext_query_removes_operators_and_bounds_terms() -> None:
    malicious = "cache:(miss OR hit) AND title:* } MATCH (n) DETACH DELETE n //"

    value = sanitize_fulltext_query(malicious)

    assert ":" not in value
    assert "*" not in value
    assert "{" not in value
    assert len(value.split()) <= 32


def test_request_enforces_graph_and_context_bounds() -> None:
    with pytest.raises(ValidationError):
        RetrievalRequest(
            question="Why did latency rise?",
            target_service="gateway",
            cutoff=datetime.now(UTC),
            authorized_service_ids=("svc-gateway",),
            graph_depth=3,
            graph_node_cap=51,
            final_chunk_limit=9,
            final_token_budget=5_001,
        )


def test_rrf_uses_rank_not_incomparable_raw_scores() -> None:
    alpha = candidate("alpha", score=0.99)
    beta = candidate("beta", score=0.20)
    lexical_alpha = alpha.model_copy(update={"vector_score": None, "lexical_score": 1.0})
    lexical_beta = beta.model_copy(update={"vector_score": None, "lexical_score": 20.0})

    fused = reciprocal_rank_fusion([alpha, beta], [lexical_beta, lexical_alpha])

    assert {item.source_id for item in fused[:2]} == {"alpha", "beta"}
    assert fused[0].fused_score == fused[1].fused_score
    assert all(item.fused_score < 0.04 for item in fused)


def test_context_is_deduplicated_and_strictly_budgeted() -> None:
    duplicate = candidate("alpha").model_copy(update={"chunk_id": "chunk-alpha-2"})
    selected = select_context(
        [candidate("alpha", tokens=200), duplicate, candidate("beta", tokens=400)],
        chunk_limit=8,
        token_budget=500,
    )

    assert [item.source_id for item in selected] == ["alpha"]
    assert sum(item.token_count for item in selected) <= 500


def test_metrics_are_graded_and_cut_off_at_five() -> None:
    metrics = retrieval_metrics(
        ["irrelevant", "primary", "secondary", "x", "y", "late"],
        {"primary": 2, "secondary": 1, "late": 2},
    )

    assert metrics["recall_at_5"] == pytest.approx(2 / 3)
    assert metrics["mrr_at_5"] == pytest.approx(0.5)
    assert 0 < metrics["ndcg_at_5"] < 1


def test_heldout_seal_detects_any_change(tmp_path: Path) -> None:
    questions = tmp_path / "questions.jsonl"
    labels = tmp_path / "labels.jsonl"
    seal = tmp_path / "seal.json"
    question_rows = [
        {"question_id": f"d{index}", "split": "dev", "group_id": f"dg{index}"}
        for index in range(20)
    ] + [
        {"question_id": f"h{index}", "split": "heldout", "group_id": f"hg{index}"}
        for index in range(20)
    ]
    label_rows = [
        {"question_id": item["question_id"], "relevance": {"doc": 2}} for item in question_rows
    ]
    questions.write_text(
        "\n".join(json.dumps(item) for item in question_rows) + "\n", encoding="utf-8"
    )
    labels.write_text("\n".join(json.dumps(item) for item in label_rows) + "\n", encoding="utf-8")
    digest = heldout_digest(questions, labels)
    seal.write_text(
        json.dumps({"digest": digest, "question_count": 20, "label_count": 20}),
        encoding="utf-8",
    )

    assert verify_heldout_seal(questions, labels, seal)["status"] == "pass"
    label_rows[-1]["relevance"] = {"doc": 1}
    labels.write_text("\n".join(json.dumps(item) for item in label_rows) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="seal"):
        verify_heldout_seal(questions, labels, seal)


def retrieval_request(variant: RetrievalVariant = RetrievalVariant.GRAPH) -> RetrievalRequest:
    return RetrievalRequest(
        question="Why did checkout requests fail?",
        target_service="gateway",
        cutoff=datetime(2026, 9, 23, 12, tzinfo=UTC),
        authorized_service_ids=("svc-gateway", "svc-checkout", "svc-payments"),
        variant=variant,
    )


def candidate_row(source_id: str = "runbook-checkout") -> dict[str, Any]:
    now = "2026-09-23T12:00:00Z"
    return {
        "chunk_id": f"chunk-{source_id}",
        "source_id": source_id,
        "source_version": "1.0.0",
        "title": "Checkout failures",
        "section": "Diagnosis",
        "text": "Inspect checkout dependency errors.",
        "token_count": 42,
        "content_hash": "e" * 64,
        "service_ids": ["svc-gateway"],
        "observed_at": now,
        "valid_from": now,
        "valid_to": None,
        "trust_status": "trusted",
        "score": 0.9,
    }


class FakeResult(list[dict[str, Any]]):
    def single(self, *, strict: bool = False) -> dict[str, Any] | None:
        assert strict
        return self[0] if self else None


class FakeSession:
    def __init__(self, handler: Any) -> None:
        self.handler = handler

    def __enter__(self) -> FakeSession:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def run(self, query: str, **parameters: Any) -> FakeResult:
        return FakeResult(self.handler(query, parameters))


class FakeDriver:
    def __init__(self, handler: Any) -> None:
        self.handler = handler
        self.verified = False
        self.closed = False

    def session(self) -> FakeSession:
        return FakeSession(self.handler)

    def verify_connectivity(self) -> None:
        self.verified = True

    def close(self) -> None:
        self.closed = True


def bare_retriever(handler: Any) -> tuple[Neo4jRetriever, FakeDriver]:
    retriever = object.__new__(Neo4jRetriever)
    retriever.settings = SimpleNamespace(
        corpus_id="incidentgraph-corpus",
        embedding_model_revision="revision-1",
    )
    retriever.embedder = SimpleNamespace(encode=lambda _: [[0.1, 0.2]])
    driver = FakeDriver(handler)
    retriever.driver = driver
    return retriever, driver


def test_retriever_driver_helpers_are_bounded_and_fail_closed() -> None:
    def handler(query: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
        if "MATCH (corpus:Corpus" in query:
            return [{"version": "corpus-v1", "embedding_model": "local-test-model"}]
        if "RETURN DISTINCT service.id" in query:
            name = parameters["name"]
            if name == "ambiguous":
                return [{"id": "svc-a"}, {"id": "svc-b"}]
            if name == "missing":
                return []
            return [{"id": "svc-gateway"}]
        if "MATCH path=" in query:
            return [
                {
                    "id": "svc-checkout",
                    "node_ids": ["svc-gateway", "svc-checkout"],
                    "relationships": [
                        {
                            "type": "DEPENDS_ON",
                            "caller": "svc-gateway",
                            "callee": "svc-checkout",
                            "source_id": "topology-v1",
                            "topology_version": "1",
                        }
                    ],
                    "hops": 1,
                },
                {
                    "id": "svc-payments",
                    "node_ids": ["svc-gateway", "svc-checkout", "svc-payments"],
                    "relationships": [],
                    "hops": 2,
                },
                {
                    "id": "svc-unauthorized",
                    "node_ids": ["svc-gateway", "svc-unauthorized"],
                    "relationships": [],
                    "hops": 1,
                },
                {
                    "id": "svc-loop",
                    "node_ids": ["svc-gateway", "svc-gateway"],
                    "relationships": [],
                    "hops": 2,
                },
            ]
        if "SEARCH chunk IN" in query:
            return [candidate_row()]
        raise AssertionError(query)

    retriever, driver = bare_retriever(handler)
    with retriever as entered:
        assert entered is retriever
    assert driver.verified and driver.closed
    assert retriever._corpus_metadata() == ("corpus-v1", "local-test-model")
    assert retriever._resolve_service("gateway", "lab") == "svc-gateway"
    with pytest.raises(RetrievalError, match="not found"):
        retriever._resolve_service("missing", "lab")
    with pytest.raises(RetrievalError, match="ambiguous"):
        retriever._resolve_service("ambiguous", "lab")

    direct_request = retrieval_request().model_copy(update={"graph_depth": 0})
    service_ids, paths = retriever._graph_scope("svc-gateway", direct_request)
    assert service_ids == ("svc-gateway",)
    assert paths["svc-gateway"].hops == 0

    service_ids, paths = retriever._graph_scope("svc-gateway", retrieval_request())
    assert service_ids == ("svc-gateway", "svc-checkout", "svc-payments")
    assert paths["svc-checkout"].relationships[0]["type"] == "DEPENDS_ON"

    vector = retriever._vector_search([0.1, 0.2], retrieval_request(), service_ids)
    lexical = retriever._lexical_search(retrieval_request(), service_ids)
    assert vector[0].vector_score == 0.9
    assert lexical[0].lexical_score == 0.9


def test_missing_corpus_metadata_is_reported() -> None:
    retriever, _ = bare_retriever(lambda *_: [])
    with pytest.raises(RetrievalError, match="not been ingested"):
        retriever._corpus_metadata()


class HarnessRetriever(Neo4jRetriever):
    def __init__(self) -> None:
        self.settings = SimpleNamespace(
            corpus_id="incidentgraph-corpus",
            embedding_model_revision="revision-1",
        )
        self.embedder = SimpleNamespace(encode=lambda _: [[0.1, 0.2]])

    def _resolve_service(self, name: str, environment: str) -> str:
        del name, environment
        return "svc-gateway"

    def _corpus_metadata(self) -> tuple[str, str]:
        return "corpus-v1", "local-test-model"

    def _graph_scope(
        self, target_id: str, request: RetrievalRequest
    ) -> tuple[tuple[str, ...], dict[str, GraphPath]]:
        del target_id, request
        return (
            ("svc-gateway", "svc-payments"),
            {
                "svc-gateway": GraphPath(node_ids=("svc-gateway",), relationships=(), hops=0),
                "svc-payments": GraphPath(
                    node_ids=("svc-gateway", "svc-payments"),
                    relationships=(
                        {
                            "type": "DEPENDS_ON",
                            "caller": "svc-gateway",
                            "callee": "svc-payments",
                        },
                    ),
                    hops=1,
                ),
            },
        )

    def _vector_search(
        self,
        embedding: Any,
        request: RetrievalRequest,
        service_ids: Any,
    ) -> list[RetrievalCandidate]:
        del embedding, request, service_ids
        return [candidate("runbook-gateway", score=0.9)]

    def _lexical_search(
        self, request: RetrievalRequest, service_ids: Any
    ) -> list[RetrievalCandidate]:
        del request, service_ids
        return [
            candidate("incident-payments", score=0.8).model_copy(
                update={
                    "service_ids": ("svc-payments",),
                    "vector_score": None,
                    "lexical_score": 0.8,
                }
            )
        ]


@pytest.mark.parametrize("variant", list(RetrievalVariant))
def test_retrieve_executes_each_runtime_variant(variant: RetrievalVariant) -> None:
    result = HarnessRetriever().retrieve(retrieval_request(variant))

    assert result.corpus_version == "corpus-v1"
    assert result.embedding_revision == "revision-1"
    assert result.vector_ranking[0].rank == 1
    assert result.selected_token_count > 0
    assert result.evidence[0].query_template_id == f"phase4-{variant}-v1"
    if variant == RetrievalVariant.VECTOR:
        assert result.lexical_ranking == ()
        assert len(result.selected_candidates) == 1
    else:
        assert len(result.lexical_ranking) == 1
        assert len(result.selected_candidates) == 2
    if variant == RetrievalVariant.GRAPH:
        incident = next(item for item in result.evidence if item.source_id.startswith("incident-"))
        assert incident.kind == "reviewed_incident"
        assert "DEPENDS_ON" in incident.provenance_reference


def test_retrieve_rejects_target_outside_authorization() -> None:
    unauthorized = retrieval_request().model_copy(
        update={"authorized_service_ids": ("svc-checkout",)}
    )
    with pytest.raises(RetrievalError, match="outside authorization"):
        HarnessRetriever().retrieve(unauthorized)


def test_request_rejects_naive_cutoff_and_duplicate_scope() -> None:
    payload = retrieval_request().model_dump()
    payload["cutoff"] = datetime(2026, 9, 23)
    with pytest.raises(ValidationError, match="UTC offset"):
        RetrievalRequest.model_validate(payload)

    payload = retrieval_request().model_dump()
    payload["authorized_service_ids"] = ("svc-gateway", "svc-gateway")
    with pytest.raises(ValidationError, match="duplicates"):
        RetrievalRequest.model_validate(payload)
