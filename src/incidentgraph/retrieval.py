from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import re
import shutil
import subprocess
import time
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal
from uuid import NAMESPACE_URL, uuid5

from neo4j import GraphDatabase
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from incidentgraph.config import Settings
from incidentgraph.ingestion import FULLTEXT_INDEX, ROOT, VECTOR_INDEX, LocalSentenceEmbedder
from incidentgraph.models import EvidenceItem

QUESTION_PATH = ROOT / "data" / "evaluation" / "retrieval-questions-v1.jsonl"
LABEL_PATH = ROOT / "data" / "evaluator" / "retrieval-labels-v1.jsonl"
SEAL_PATH = ROOT / "data" / "evaluator" / "retrieval-heldout-seal-v1.json"
DEFAULT_EVALUATION_DIR = ROOT / "artifacts" / "evaluation" / "phase4-dev"
TRUSTED_STATUSES = ("trusted", "reviewed", "reference")
RRF_K = 60
FULLTEXT_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_]{1,63}")


class RetrievalError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class RetrievalVariant(StrEnum):
    VECTOR = "vector"
    HYBRID = "hybrid"
    GRAPH = "graph"


class RetrievalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    question: str = Field(min_length=3, max_length=2_000)
    target_service: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
    environment: Literal["lab"] = "lab"
    cutoff: datetime
    authorized_service_ids: tuple[str, ...] = Field(min_length=1, max_length=50)
    variant: RetrievalVariant = RetrievalVariant.GRAPH
    vector_candidates: int = Field(default=20, ge=1, le=50)
    lexical_candidates: int = Field(default=20, ge=1, le=50)
    graph_depth: int = Field(default=2, ge=0, le=2)
    graph_node_cap: int = Field(default=50, ge=1, le=50)
    final_chunk_limit: int = Field(default=8, ge=1, le=8)
    final_token_budget: int = Field(default=5_000, ge=1, le=5_000)

    @field_validator("cutoff")
    @classmethod
    def normalize_cutoff(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("cutoff must include a UTC offset")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def unique_authorization_scope(self) -> RetrievalRequest:
        if len(set(self.authorized_service_ids)) != len(self.authorized_service_ids):
            raise ValueError("authorized_service_ids contains duplicates")
        return self


class GraphPath(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    node_ids: tuple[str, ...]
    relationships: tuple[dict[str, str], ...]
    hops: int = Field(ge=0, le=2)


class RetrievalCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: str
    source_id: str
    source_version: str
    title: str
    section: str
    text: str
    token_count: int
    content_hash: str
    service_ids: tuple[str, ...]
    observed_at: datetime
    valid_from: datetime
    valid_to: datetime | None
    trust_status: str
    vector_score: float | None = None
    lexical_score: float | None = None
    vector_rank: int | None = None
    lexical_rank: int | None = None
    fused_score: float = 0.0
    graph_path: GraphPath | None = None


class RankingEntry(BaseModel):
    chunk_id: str
    source_id: str
    rank: int = Field(ge=1)
    score: float


class RetrievalResult(BaseModel):
    request: RetrievalRequest
    resolved_target_service_id: str
    corpus_id: str
    corpus_version: str
    embedding_model: str
    embedding_revision: str
    vector_ranking: tuple[RankingEntry, ...]
    lexical_ranking: tuple[RankingEntry, ...]
    selected_candidates: tuple[RetrievalCandidate, ...]
    evidence: tuple[EvidenceItem, ...]
    selected_token_count: int
    elapsed_ms: float


class EvaluationQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    question_id: str
    split: Literal["dev", "heldout"]
    group_id: str
    question: str
    target_service: str
    environment: Literal["lab"]
    cutoff: datetime
    authorized_service_ids: tuple[str, ...]


class EvaluationLabel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    question_id: str
    relevance: dict[str, int]
    annotation_version: str


def sanitize_fulltext_query(question: str) -> str:
    """Convert untrusted text to a bounded, operator-free Lucene term query."""
    terms = [term.lower() for term in FULLTEXT_TOKEN.findall(question)][:32]
    if not terms:
        raise RetrievalError("INVALID_ARGUMENT", "question contains no searchable terms")
    return " ".join(terms)


def reciprocal_rank_fusion(
    vector: Sequence[RetrievalCandidate],
    lexical: Sequence[RetrievalCandidate],
    *,
    k: int = RRF_K,
) -> list[RetrievalCandidate]:
    by_id: dict[str, RetrievalCandidate] = {}
    vector_ranks = {item.chunk_id: rank for rank, item in enumerate(vector, start=1)}
    lexical_ranks = {item.chunk_id: rank for rank, item in enumerate(lexical, start=1)}
    for item in (*vector, *lexical):
        current = by_id.get(item.chunk_id, item)
        vector_rank = vector_ranks.get(item.chunk_id)
        lexical_rank = lexical_ranks.get(item.chunk_id)
        score = (1 / (k + vector_rank) if vector_rank is not None else 0.0) + (
            1 / (k + lexical_rank) if lexical_rank is not None else 0.0
        )
        vector_score = next(
            (candidate.vector_score for candidate in vector if candidate.chunk_id == item.chunk_id),
            None,
        )
        lexical_score = next(
            (
                candidate.lexical_score
                for candidate in lexical
                if candidate.chunk_id == item.chunk_id
            ),
            None,
        )
        by_id[item.chunk_id] = current.model_copy(
            update={
                "vector_rank": vector_rank,
                "lexical_rank": lexical_rank,
                "vector_score": vector_score,
                "lexical_score": lexical_score,
                "fused_score": score,
            }
        )
    return sorted(
        by_id.values(),
        key=lambda item: (-item.fused_score, item.source_id, item.chunk_id),
    )


def select_context(
    candidates: Iterable[RetrievalCandidate], *, chunk_limit: int, token_budget: int
) -> list[RetrievalCandidate]:
    selected: list[RetrievalCandidate] = []
    sources: set[str] = set()
    content_hashes: set[str] = set()
    tokens = 0
    for candidate in candidates:
        if candidate.source_id in sources or candidate.content_hash in content_hashes:
            continue
        if tokens + candidate.token_count > token_budget:
            continue
        selected.append(candidate)
        sources.add(candidate.source_id)
        content_hashes.add(candidate.content_hash)
        tokens += candidate.token_count
        if len(selected) == chunk_limit:
            break
    return selected


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: Any) -> datetime:
    if not isinstance(value, str):
        raise TypeError(f"expected ISO datetime string, got {type(value).__name__}")
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _candidate(row: dict[str, Any], signal: Literal["vector", "lexical"]) -> RetrievalCandidate:
    score = float(row["score"])
    return RetrievalCandidate(
        chunk_id=str(row["chunk_id"]),
        source_id=str(row["source_id"]),
        source_version=str(row["source_version"]),
        title=str(row["title"]),
        section=str(row["section"]),
        text=str(row["text"]),
        token_count=int(row["token_count"]),
        content_hash=str(row["content_hash"]),
        service_ids=tuple(sorted(str(item) for item in row["service_ids"])),
        observed_at=_parse_datetime(row["observed_at"]),
        valid_from=_parse_datetime(row["valid_from"]),
        valid_to=_parse_datetime(row["valid_to"]) if row["valid_to"] else None,
        trust_status=str(row["trust_status"]),
        vector_score=score if signal == "vector" else None,
        lexical_score=score if signal == "lexical" else None,
        fused_score=score if signal == "vector" else 0.0,
    )


class Neo4jRetriever:
    def __init__(
        self,
        settings: Settings,
        embedder: LocalSentenceEmbedder | None = None,
    ) -> None:
        self.settings = settings
        self.embedder = embedder or LocalSentenceEmbedder(settings)
        self.driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
        )

    def close(self) -> None:
        self.driver.close()

    def __enter__(self) -> Neo4jRetriever:
        self.driver.verify_connectivity()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _corpus_metadata(self) -> tuple[str, str]:
        with self.driver.session() as session:
            row = session.run(
                "MATCH (corpus:Corpus {id: $corpus_id}) "
                "RETURN corpus.version AS version, corpus.embedding_model AS embedding_model",
                corpus_id=self.settings.corpus_id,
            ).single(strict=True)
        if row is None:
            raise RetrievalError("NOT_FOUND", "configured corpus has not been ingested")
        return str(row["version"]), str(row["embedding_model"])

    def _resolve_service(self, name: str, environment: str) -> str:
        with self.driver.session() as session:
            rows = list(
                session.run(
                    "MATCH (service:Service {environment: $environment}) "
                    "WHERE toLower(service.id)=toLower($name) "
                    "OR toLower(service.name)=toLower($name) "
                    "OR any(alias IN service.aliases WHERE toLower(alias)=toLower($name)) "
                    "RETURN DISTINCT service.id AS id ORDER BY id",
                    environment=environment,
                    name=name,
                )
            )
        if not rows:
            raise RetrievalError("NOT_FOUND", f"service not found: {name}")
        if len(rows) > 1:
            raise RetrievalError("AMBIGUOUS_SERVICE", f"service alias is ambiguous: {name}")
        return str(rows[0]["id"])

    def _graph_scope(
        self, target_id: str, request: RetrievalRequest
    ) -> tuple[tuple[str, ...], dict[str, GraphPath]]:
        direct = GraphPath(node_ids=(target_id,), relationships=(), hops=0)
        paths: dict[str, GraphPath] = {target_id: direct}
        if request.graph_depth == 0:
            return (target_id,), paths
        query = (
            "MATCH path=(target:Service {id: $target_id, environment: $environment})"
            f"-[:DEPENDS_ON*1..{request.graph_depth}]-(neighbor:Service) "
            "WHERE all(rel IN relationships(path) WHERE rel.valid_from <= $cutoff "
            "AND (rel.valid_to IS NULL OR $cutoff < rel.valid_to)) "
            "AND all(node IN nodes(path) WHERE node.environment = $environment) "
            "RETURN neighbor.id AS id, [node IN nodes(path) | node.id] AS node_ids, "
            "[rel IN relationships(path) | {type: type(rel), caller: startNode(rel).id, "
            "callee: endNode(rel).id, source_id: rel.source_id, "
            "topology_version: rel.topology_version}] AS relationships, "
            "length(path) AS hops ORDER BY hops, id LIMIT $node_cap"
        )
        with self.driver.session() as session:
            rows = session.run(
                query,
                target_id=target_id,
                environment=request.environment,
                cutoff=_iso(request.cutoff),
                node_cap=request.graph_node_cap,
            )
            for row in rows:
                node_ids = tuple(str(value) for value in row["node_ids"])
                if len(node_ids) != len(set(node_ids)):
                    continue
                service_id = str(row["id"])
                if service_id not in request.authorized_service_ids or service_id in paths:
                    continue
                paths[service_id] = GraphPath(
                    node_ids=node_ids,
                    relationships=tuple(
                        {str(key): str(value) for key, value in dict(rel).items()}
                        for rel in row["relationships"]
                    ),
                    hops=int(row["hops"]),
                )
        ordered = tuple(
            item[0] for item in sorted(paths.items(), key=lambda item: (item[1].hops, item[0]))
        )
        return ordered, paths

    @staticmethod
    def _candidate_query(index_clause: str) -> str:
        return (
            "MATCH (chunk:Chunk) "
            f"{index_clause} "
            "MATCH (doc:Document)-[:HAS_CHUNK]->(chunk) "
            "MATCH (chunk)-[:ABOUT]->(service:Service) "
            "WITH chunk, doc, score, collect(DISTINCT service.id) AS service_ids "
            "WHERE chunk.corpus_id = $corpus_id AND doc.corpus_id = $corpus_id "
            "AND doc.archived_at IS NULL AND doc.trust_status IN $trusted_statuses "
            "AND doc.valid_from <= $cutoff AND (doc.valid_to IS NULL OR $cutoff < doc.valid_to) "
            "AND any(id IN service_ids WHERE id IN $service_ids) "
            "RETURN chunk.id AS chunk_id, doc.source_id AS source_id, "
            "doc.document_version AS source_version, doc.title AS title, "
            "chunk.section AS section, chunk.text AS text, chunk.token_count AS token_count, "
            "chunk.content_hash AS content_hash, service_ids, doc.observed_at AS observed_at, "
            "doc.valid_from AS valid_from, doc.valid_to AS valid_to, "
            "doc.trust_status AS trust_status, score ORDER BY score DESC LIMIT $candidate_limit"
        )

    def _vector_search(
        self,
        embedding: Sequence[float],
        request: RetrievalRequest,
        service_ids: Sequence[str],
    ) -> list[RetrievalCandidate]:
        oversample = min(200, max(80, request.vector_candidates * 4))
        clause = (
            f"SEARCH chunk IN (VECTOR INDEX {VECTOR_INDEX} "
            f"FOR $embedding LIMIT {oversample}) SCORE AS score"
        )
        with self.driver.session() as session:
            rows = session.run(
                self._candidate_query(clause),
                embedding=list(embedding),
                corpus_id=self.settings.corpus_id,
                trusted_statuses=list(TRUSTED_STATUSES),
                cutoff=_iso(request.cutoff),
                service_ids=list(service_ids),
                candidate_limit=request.vector_candidates,
            )
            return [_candidate(dict(row), "vector") for row in rows]

    def _lexical_search(
        self, request: RetrievalRequest, service_ids: Sequence[str]
    ) -> list[RetrievalCandidate]:
        oversample = min(200, max(80, request.lexical_candidates * 4))
        clause = (
            f"SEARCH chunk IN (FULLTEXT INDEX {FULLTEXT_INDEX} "
            f"FOR $search_text LIMIT {oversample}) SCORE AS score"
        )
        with self.driver.session() as session:
            rows = session.run(
                self._candidate_query(clause),
                search_text=sanitize_fulltext_query(request.question),
                corpus_id=self.settings.corpus_id,
                trusted_statuses=list(TRUSTED_STATUSES),
                cutoff=_iso(request.cutoff),
                service_ids=list(service_ids),
                candidate_limit=request.lexical_candidates,
            )
            return [_candidate(dict(row), "lexical") for row in rows]

    @staticmethod
    def _attach_paths(
        candidates: Sequence[RetrievalCandidate], paths: dict[str, GraphPath]
    ) -> list[RetrievalCandidate]:
        output: list[RetrievalCandidate] = []
        for candidate in candidates:
            available = [paths[item] for item in candidate.service_ids if item in paths]
            path = (
                min(available, key=lambda item: (item.hops, item.node_ids)) if available else None
            )
            output.append(candidate.model_copy(update={"graph_path": path}))
        return output

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        started = time.perf_counter()
        target_id = self._resolve_service(request.target_service, request.environment)
        if target_id not in request.authorized_service_ids:
            raise RetrievalError("UNAUTHORIZED", f"service is outside authorization: {target_id}")
        corpus_version, embedding_model = self._corpus_metadata()
        service_ids: tuple[str, ...] = (target_id,)
        paths = {target_id: GraphPath(node_ids=(target_id,), relationships=(), hops=0)}
        if request.variant == RetrievalVariant.GRAPH:
            service_ids, paths = self._graph_scope(target_id, request)

        embedding = self.embedder.encode([request.question])[0]
        vector = self._vector_search(embedding, request, service_ids)
        lexical: list[RetrievalCandidate] = []
        if request.variant != RetrievalVariant.VECTOR:
            lexical = self._lexical_search(request, service_ids)
            ranked = reciprocal_rank_fusion(vector, lexical)
        else:
            ranked = [
                item.model_copy(
                    update={"vector_rank": rank, "fused_score": float(item.vector_score or 0)}
                )
                for rank, item in enumerate(vector, start=1)
            ]
        if request.variant == RetrievalVariant.GRAPH:
            ranked = self._attach_paths(ranked, paths)
        selected = select_context(
            ranked,
            chunk_limit=request.final_chunk_limit,
            token_budget=request.final_token_budget,
        )
        evidence = tuple(
            self._to_evidence(item, request, target_id, corpus_version) for item in selected
        )
        return RetrievalResult(
            request=request,
            resolved_target_service_id=target_id,
            corpus_id=self.settings.corpus_id,
            corpus_version=corpus_version,
            embedding_model=embedding_model,
            embedding_revision=self.settings.embedding_model_revision,
            vector_ranking=tuple(
                RankingEntry(
                    chunk_id=item.chunk_id,
                    source_id=item.source_id,
                    rank=rank,
                    score=float(item.vector_score or 0),
                )
                for rank, item in enumerate(vector, start=1)
            ),
            lexical_ranking=tuple(
                RankingEntry(
                    chunk_id=item.chunk_id,
                    source_id=item.source_id,
                    rank=rank,
                    score=float(item.lexical_score or 0),
                )
                for rank, item in enumerate(lexical, start=1)
            ),
            selected_candidates=tuple(selected),
            evidence=evidence,
            selected_token_count=sum(item.token_count for item in selected),
            elapsed_ms=round((time.perf_counter() - started) * 1_000, 3),
        )

    def _to_evidence(
        self,
        candidate: RetrievalCandidate,
        request: RetrievalRequest,
        target_id: str,
        corpus_version: str,
    ) -> EvidenceItem:
        path_json = (
            json.dumps(candidate.graph_path.model_dump(mode="json"), sort_keys=True)
            if candidate.graph_path
            else "direct-service-scope"
        )
        identity = f"{candidate.chunk_id}|{corpus_version}|{request.variant}|{path_json}"
        return EvidenceItem(
            evidence_id=uuid5(NAMESPACE_URL, f"incidentgraph://evidence/{identity}"),
            kind="reviewed_incident" if candidate.source_id.startswith("incident-") else "document",
            source_id=candidate.source_id,
            source_version=candidate.source_version,
            service_ids=list(candidate.service_ids),
            environment=request.environment,
            observed_at=candidate.observed_at,
            collected_at=request.cutoff,
            content_hash=candidate.content_hash,
            freshness_status="fresh",
            limitations=["retrieval evidence; factual use still requires claim-level verification"],
            provenance_reference=(
                f"neo4j://corpus/{self.settings.corpus_id}/chunk/{candidate.chunk_id};"
                f"variant={request.variant};target={target_id};path={path_json}"
            ),
            valid_from=candidate.valid_from,
            valid_to=candidate.valid_to,
            snapshot_id=corpus_version,
            query_template_id=f"phase4-{request.variant}-v1",
            safe_parameters={
                "target_service_id": target_id,
                "environment": request.environment,
                "cutoff": _iso(request.cutoff),
                "authorized_service_ids": sorted(request.authorized_service_ids),
            },
            content=candidate.text,
        )


def retrieval_metrics(
    ranked_source_ids: Sequence[str], relevance: dict[str, int]
) -> dict[str, float]:
    ranked = list(dict.fromkeys(ranked_source_ids))[:5]
    relevant = {source_id for source_id, grade in relevance.items() if grade > 0}
    hits = len(relevant.intersection(ranked))
    recall = hits / len(relevant) if relevant else 0.0
    reciprocal_rank = next(
        (1 / rank for rank, source_id in enumerate(ranked, start=1) if source_id in relevant),
        0.0,
    )
    dcg = sum(
        (2 ** relevance.get(source_id, 0) - 1) / math.log2(rank + 1)
        for rank, source_id in enumerate(ranked, start=1)
    )
    ideal = sorted((grade for grade in relevance.values() if grade > 0), reverse=True)[:5]
    idcg = sum((2**grade - 1) / math.log2(rank + 1) for rank, grade in enumerate(ideal, start=1))
    return {
        "recall_at_5": recall,
        "mrr_at_5": reciprocal_rank,
        "ndcg_at_5": dcg / idcg if idcg else 0.0,
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def heldout_digest(question_path: Path = QUESTION_PATH, label_path: Path = LABEL_PATH) -> str:
    questions = [
        line
        for line in question_path.read_text(encoding="utf-8").splitlines()
        if json.loads(line)["split"] == "heldout"
    ]
    ids = {json.loads(line)["question_id"] for line in questions}
    labels = [
        line
        for line in label_path.read_text(encoding="utf-8").splitlines()
        if json.loads(line)["question_id"] in ids
    ]
    payload = "\n".join(questions) + "\n---LABELS---\n" + "\n".join(labels) + "\n"
    return hashlib.sha256(payload.encode()).hexdigest()


def verify_heldout_seal(
    question_path: Path = QUESTION_PATH,
    label_path: Path = LABEL_PATH,
    seal_path: Path = SEAL_PATH,
) -> dict[str, Any]:
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    question_rows = _read_jsonl(question_path)
    label_rows = _read_jsonl(label_path)
    dev_questions = [item for item in question_rows if item["split"] == "dev"]
    heldout_questions = [item for item in question_rows if item["split"] == "heldout"]
    question_ids = {item["question_id"] for item in question_rows}
    label_ids = {item["question_id"] for item in label_rows}
    dev_groups = {item["group_id"] for item in dev_questions}
    heldout_groups = {item["group_id"] for item in heldout_questions}
    if len(dev_questions) != 20 or len(heldout_questions) != 20:
        raise ValueError("retrieval fixture must contain exactly 20 dev and 20 held-out questions")
    if question_ids != label_ids:
        raise ValueError("retrieval question and evaluator-label IDs do not match")
    if dev_groups.intersection(heldout_groups):
        raise ValueError("development and held-out group IDs must be disjoint")
    actual = heldout_digest(question_path, label_path)
    if actual != seal["digest"]:
        raise ValueError("held-out retrieval split no longer matches its pre-tuning seal")
    if (
        len(heldout_questions) != seal["question_count"]
        or len(heldout_questions) != seal["label_count"]
    ):
        raise ValueError("held-out retrieval split counts do not match its seal")
    return {
        "status": "pass",
        "digest": actual,
        "question_count": len(heldout_questions),
        "label_count": len(heldout_questions),
        "dev_question_count": len(dev_questions),
        "groups_disjoint": True,
    }


def _git_revision() -> str:
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is required to record evaluation provenance")
    result = subprocess.run(  # noqa: S603 - fixed arguments and resolved git executable
        [git, "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def evaluate_dev(settings: Settings, output_dir: Path = DEFAULT_EVALUATION_DIR) -> dict[str, Any]:
    seal = verify_heldout_seal()
    questions = [
        EvaluationQuestion.model_validate(item)
        for item in _read_jsonl(QUESTION_PATH)
        if item["split"] == "dev"
    ]
    all_labels = {
        item["question_id"]: EvaluationLabel.model_validate(item)
        for item in _read_jsonl(LABEL_PATH)
    }
    if len(questions) != 20:
        raise ValueError(f"expected 20 development questions, found {len(questions)}")
    rows: list[dict[str, Any]] = []
    with Neo4jRetriever(settings) as retriever:
        for question in questions:
            label = all_labels[question.question_id]
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
                metrics = retrieval_metrics(ranked, label.relevance)
                rows.append(
                    {
                        "question_id": question.question_id,
                        "group_id": question.group_id,
                        "variant": variant.value,
                        **metrics,
                        "top_5_source_ids": ranked[:5],
                        "selected_token_count": result.selected_token_count,
                        "graph_paths": [
                            {
                                "source_id": item.source_id,
                                "path": item.graph_path.model_dump(mode="json"),
                            }
                            for item in result.selected_candidates[:5]
                            if item.graph_path is not None
                        ],
                        "corpus_version": result.corpus_version,
                        "elapsed_ms": result.elapsed_ms,
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

    graph_case = [row for row in rows if row["question_id"] == "rq-dev-004"]
    direct_relevant = {"doc-payments-cache-contract", "runbook-cache"}
    graph_demo = {
        row["variant"]: bool(direct_relevant.intersection(row["top_5_source_ids"]))
        for row in graph_case
    }
    graph_demo_paths = next(
        row["graph_paths"] for row in graph_case if row["variant"] == RetrievalVariant.GRAPH.value
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    result_document = {
        "schema_version": 1,
        "split": "dev",
        "heldout": {**seal, "evaluated": False},
        "question_count": len(questions),
        "variants": [item.value for item in RetrievalVariant],
        "candidate_limits": {"vector": 20, "fulltext": 20},
        "graph_limits": {"depth": 2, "node_cap": 50, "allowed_relationships": ["DEPENDS_ON"]},
        "context_limits": {"chunks": 8, "tokens": 5_000},
        "rrf_k": RRF_K,
        "model_calls": 0,
        "model_cost_usd": 0,
        "embedding_model": f"{settings.embedding_model_id}@{settings.embedding_model_revision}",
        "hardware": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "device": settings.embedding_device,
        },
        "git_revision": _git_revision(),
        "aggregate": aggregate,
        "graph_required_case_rq_dev_004": graph_demo,
        "graph_required_case_paths": graph_demo_paths,
        "rows": rows,
    }
    (output_dir / "results.json").write_text(
        json.dumps(result_document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with (output_dir / "per-question.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "question_id",
                "group_id",
                "variant",
                "recall_at_5",
                "mrr_at_5",
                "ndcg_at_5",
                "elapsed_ms",
                "selected_token_count",
                "top_5_source_ids",
                "corpus_version",
            ],
        )
        writer.writeheader()
        for row in rows:
            csv_row = {key: value for key, value in row.items() if key != "graph_paths"}
            writer.writerow({**csv_row, "top_5_source_ids": "|".join(row["top_5_source_ids"])})
    lines = [
        "# Phase 4 development retrieval evaluation",
        "",
        "Held-out was seal-verified and was not evaluated.",
        "",
        "| Variant | Recall@5 | MRR@5 | nDCG@5 | Mean ms |",
        "|---|---:|---:|---:|---:|",
    ]
    for variant_name, metrics in aggregate.items():
        lines.append(
            f"| {variant_name} | {metrics['recall_at_5']:.3f} | {metrics['mrr_at_5']:.3f} | "
            f"{metrics['ndcg_at_5']:.3f} | {metrics['mean_elapsed_ms']:.1f} |"
        )
    lines.extend(
        [
            "",
            "## Required graph-only case",
            "",
            f"`rq-dev-004`: `{json.dumps(graph_demo, sort_keys=True)}`",
            "",
            "The machine-readable `results.json` records exact node and relationship paths.",
            "",
        ]
    )
    (output_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    return result_document


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="IncidentGraph bounded retrieval and evaluation")
    sub = parser.add_subparsers(dest="command", required=True)
    search = sub.add_parser("search")
    search.add_argument("--query", required=True)
    search.add_argument("--service", required=True)
    search.add_argument(
        "--variant", choices=[item.value for item in RetrievalVariant], default="graph"
    )
    search.add_argument("--cutoff", default="2026-09-23T12:00:00Z")
    search.add_argument("--authorize", action="append", required=True)
    evaluate = sub.add_parser("evaluate-dev")
    evaluate.add_argument("--output-dir", type=Path, default=DEFAULT_EVALUATION_DIR)
    sub.add_parser("verify")
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "verify":
        print(json.dumps(verify_heldout_seal(), indent=2, sort_keys=True))
        return
    settings = Settings()  # type: ignore[call-arg]
    if args.command == "evaluate-dev":
        eval_result = evaluate_dev(settings, args.output_dir)
        print(
            json.dumps(
                {
                    "aggregate": eval_result["aggregate"],
                    "heldout": eval_result["heldout"],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return
    request = RetrievalRequest(
        question=args.query,
        target_service=args.service,
        cutoff=datetime.fromisoformat(args.cutoff.replace("Z", "+00:00")),
        authorized_service_ids=tuple(args.authorize),
        variant=args.variant,
    )
    with Neo4jRetriever(settings) as retriever:
        search_result = retriever.retrieve(request)
    print(search_result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
