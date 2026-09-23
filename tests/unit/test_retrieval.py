from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from incidentgraph.retrieval import (
    GraphPath,
    RetrievalCandidate,
    RetrievalRequest,
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
