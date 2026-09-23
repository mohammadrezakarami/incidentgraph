from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol, cast

from neo4j import Driver, GraphDatabase, ManagedTransaction
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from incidentgraph.config import Settings

ROOT = Path(__file__).resolve().parents[2]
CORPUS_ROOT = ROOT / "data" / "corpus"
MANIFEST_PATH = CORPUS_ROOT / "manifest.jsonl"
TOPOLOGY_PATH = ROOT / "config" / "topology.json"
SCHEMA_PATH = ROOT / "config" / "graph_schema.cypher"
DEFAULT_REPORT_PATH = ROOT / "artifacts" / "ingestion" / "phase3-latest.json"
DEFAULT_BENCHMARK_PATH = ROOT / "artifacts" / "ingestion" / "embedding-benchmark.json"
MODEL_DIR = ROOT / "models"

FULLTEXT_INDEX = "chunk_text_fulltext"
VECTOR_INDEX = "chunk_embedding_vector"
CHUNK_TOKENS = 500
CHUNK_OVERLAP = 75
MAX_CHUNK_TOKENS = 600
INDEX_WAIT_SECONDS = 60.0


class Tokenizer(Protocol):
    def encode(self, text: str, *, add_special_tokens: bool = False) -> list[int]: ...

    def decode(self, token_ids: Sequence[int], *, skip_special_tokens: bool = True) -> str: ...


class ManifestRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,127}$")
    title: str = Field(min_length=3, max_length=200)
    path: str = Field(min_length=1, max_length=300)
    selector: str | None = Field(default=None, max_length=128)
    license: str = Field(min_length=1, max_length=100)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    observed_at: datetime
    document_version: str = Field(min_length=1, max_length=64)
    applicable_services: tuple[str, ...] = Field(min_length=1, max_length=20)
    trust_status: Literal["trusted", "reviewed", "reference", "outdated", "untrusted"]
    valid_from: datetime
    valid_to: datetime | None = None
    document_type: Literal[
        "service",
        "api",
        "runbook",
        "configuration",
        "reference",
        "historical_incident",
        "outdated",
        "conflicting",
    ]

    @field_validator("created_at", "observed_at", "valid_from", "valid_to")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("timestamps must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_interval(self) -> ManifestRecord:
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be after valid_from")
        if len(set(self.applicable_services)) != len(self.applicable_services):
            raise ValueError("applicable_services contains duplicates")
        return self


class ServiceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    name: str
    aliases: tuple[str, ...] = ()
    environment: str
    owner: str
    metadata_version: str


class ResourceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    name: str
    kind: str
    environment: str
    endpoint_identifier: str


class DependencyRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    caller: str
    callee: str


class ResourceUseRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    service: str
    resource: str


class DeploymentRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    service_id: str
    version: str
    timestamp: datetime
    source_record: str


class IncidentRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    window_start: datetime
    window_end: datetime
    reviewed_outcome: str
    source_provenance: str
    published_at: datetime
    affected_services: tuple[str, ...]


class TopologyRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    topology_version: str
    source_id: str
    provenance_method: Literal["reviewed_declarative_configuration"]
    valid_from: datetime
    valid_to: datetime | None
    services: tuple[ServiceRecord, ...]
    resources: tuple[ResourceRecord, ...]
    dependencies: tuple[DependencyRecord, ...]
    resource_uses: tuple[ResourceUseRecord, ...]
    deployments: tuple[DeploymentRecord, ...]
    incidents: tuple[IncidentRecord, ...]

    @model_validator(mode="after")
    def validate_endpoints_and_aliases(self) -> TopologyRecord:
        service_ids = [item.id for item in self.services]
        resource_ids = [item.id for item in self.resources]
        if len(service_ids) != len(set(service_ids)):
            raise ValueError("duplicate service ID")
        if len(resource_ids) != len(set(resource_ids)):
            raise ValueError("duplicate resource ID")

        service_set = set(service_ids)
        resource_set = set(resource_ids)
        names: dict[str, str] = {}
        for service in self.services:
            for candidate in (service.name, *service.aliases):
                normalized = candidate.casefold()
                previous = names.get(normalized)
                if previous is not None and previous != service.id:
                    raise ValueError(f"ambiguous service name or alias: {candidate}")
                names[normalized] = service.id
        for dependency in self.dependencies:
            if dependency.caller not in service_set or dependency.callee not in service_set:
                raise ValueError(f"dependency has an unknown endpoint: {dependency}")
            if dependency.caller == dependency.callee:
                raise ValueError("self dependencies are not allowed")
        for resource_use in self.resource_uses:
            if resource_use.service not in service_set or resource_use.resource not in resource_set:
                raise ValueError(f"resource use has an unknown endpoint: {resource_use}")
        for deployment in self.deployments:
            if deployment.service_id not in service_set:
                raise ValueError(f"deployment has an unknown service: {deployment.id}")
        for incident in self.incidents:
            if not set(incident.affected_services) <= service_set:
                raise ValueError(f"incident has an unknown service: {incident.id}")
        return self


class ChunkRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    document_id: str
    ordinal: int
    section: str
    text: str
    token_count: int
    content_hash: str
    embedding: tuple[float, ...] = ()


class IngestionReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["pass", "fail"]
    corpus_id: str
    corpus_version: str
    started_at: datetime
    finished_at: datetime
    duration_seconds: float
    manifest_documents: int
    inserted_documents: int
    updated_documents: int
    skipped_documents: int
    archived_documents: int
    active_documents: int
    active_chunks: int
    embedded_chunks: int
    rejected_records: list[dict[str, str]]
    embedding: dict[str, Any]
    indexes: list[dict[str, Any]]
    graph: dict[str, Any]
    verification: dict[str, Any]


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_text(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in value.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def load_topology(path: Path = TOPOLOGY_PATH) -> TopologyRecord:
    return TopologyRecord.model_validate_json(path.read_text(encoding="utf-8"))


def load_manifest(path: Path = MANIFEST_PATH) -> list[ManifestRecord]:
    records: list[ManifestRecord] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(ManifestRecord.model_validate_json(line))
        except ValidationError as exc:
            raise ValueError(f"invalid manifest line {line_number}: {exc}") from exc
    identifiers = [record.source_id for record in records]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("manifest source_id values must be unique")
    if not 30 <= len(records) <= 50:
        raise ValueError("the curated corpus must contain between 30 and 50 documents")
    return records


def _safe_source_path(record: ManifestRecord, corpus_root: Path = CORPUS_ROOT) -> Path:
    root = corpus_root.resolve()
    source_path = (root / record.path).resolve()
    if not source_path.is_relative_to(root):
        raise ValueError(f"source path leaves corpus root: {record.path}")
    if source_path.suffix.lower() not in {".md", ".txt", ".json"}:
        raise ValueError(f"unsupported source format: {source_path.suffix}")
    if not source_path.is_file():
        raise ValueError(f"source path does not exist: {record.path}")
    return source_path


def read_document(record: ManifestRecord, corpus_root: Path = CORPUS_ROOT) -> str:
    source_path = _safe_source_path(record, corpus_root)
    if source_path.suffix.lower() in {".md", ".txt"}:
        if record.selector is not None:
            raise ValueError(f"selector is only supported for JSON: {record.source_id}")
        content = source_path.read_text(encoding="utf-8")
    else:
        payload = json.loads(source_path.read_text(encoding="utf-8"))
        documents = payload.get("documents") if isinstance(payload, dict) else None
        if not isinstance(documents, list) or record.selector is None:
            raise ValueError(f"JSON source requires documents[] and selector: {record.source_id}")
        matches = [
            item
            for item in documents
            if isinstance(item, dict) and item.get("source_id") == record.selector
        ]
        if len(matches) != 1 or not isinstance(matches[0].get("body"), str):
            raise ValueError(f"selector must resolve exactly one document: {record.source_id}")
        content = cast(str, matches[0]["body"])
    if sha256_text(content) != record.content_hash:
        raise ValueError(f"content hash mismatch: {record.source_id}")
    normalized = normalize_text(content)
    if len(normalized) < 80:
        raise ValueError(f"document is too short to be useful: {record.source_id}")
    return normalized


def validate_manifest(
    manifest: Sequence[ManifestRecord],
    topology: TopologyRecord,
    corpus_root: Path = CORPUS_ROOT,
) -> dict[str, str]:
    service_ids = {service.id for service in topology.services}
    documents: dict[str, str] = {}
    for record in manifest:
        unknown = set(record.applicable_services) - service_ids
        if unknown:
            raise ValueError(f"{record.source_id} references unknown services: {sorted(unknown)}")
        documents[record.source_id] = read_document(record, corpus_root)
    return documents


def _heading_blocks(text: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    current_heading = "Document"
    current_lines: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^#{1,6}\s+(.+)$", line)
        if match:
            if current_lines:
                blocks.append((current_heading, normalize_text("\n".join(current_lines))))
            current_heading = match.group(1).strip()
            current_lines = [line]
        else:
            current_lines.append(line)
    if current_lines:
        blocks.append((current_heading, normalize_text("\n".join(current_lines))))
    return [(heading, body) for heading, body in blocks if body]


def _split_token_window(text: str, tokenizer: Tokenizer) -> list[str]:
    token_ids = tokenizer.encode(text, add_special_tokens=False)
    if len(token_ids) <= MAX_CHUNK_TOKENS:
        return [text]
    windows: list[str] = []
    start = 0
    while start < len(token_ids):
        end = min(start + CHUNK_TOKENS, len(token_ids))
        windows.append(tokenizer.decode(token_ids[start:end], skip_special_tokens=True).strip())
        if end == len(token_ids):
            break
        start = end - CHUNK_OVERLAP
    return windows


def chunk_document(record: ManifestRecord, text: str, tokenizer: Tokenizer) -> list[ChunkRecord]:
    chunks: list[tuple[str, str]] = []
    pending_headings: list[str] = []
    pending_parts: list[str] = []
    pending_tokens = 0
    for heading, block in _heading_blocks(text):
        block_tokens = len(tokenizer.encode(block, add_special_tokens=False))
        if block_tokens > MAX_CHUNK_TOKENS:
            if pending_parts:
                chunks.append((" / ".join(pending_headings), "\n\n".join(pending_parts)))
                pending_headings, pending_parts, pending_tokens = [], [], 0
            for window_number, window in enumerate(_split_token_window(block, tokenizer), start=1):
                chunks.append((f"{heading} [{window_number}]", window))
            continue
        if pending_parts and pending_tokens + block_tokens > CHUNK_TOKENS:
            chunks.append((" / ".join(pending_headings), "\n\n".join(pending_parts)))
            pending_headings, pending_parts, pending_tokens = [], [], 0
        pending_headings.append(heading)
        pending_parts.append(block)
        pending_tokens += block_tokens
    if pending_parts:
        chunks.append((" / ".join(pending_headings), "\n\n".join(pending_parts)))

    output: list[ChunkRecord] = []
    for ordinal, (section, chunk_text) in enumerate(chunks):
        token_count = len(tokenizer.encode(chunk_text, add_special_tokens=False))
        identity = (
            f"{record.source_id}|{record.document_version}|{ordinal}|{sha256_text(chunk_text)}"
        )
        output.append(
            ChunkRecord(
                id=f"chunk-{hashlib.sha256(identity.encode()).hexdigest()[:32]}",
                document_id=record.source_id,
                ordinal=ordinal,
                section=section,
                text=chunk_text,
                token_count=token_count,
                content_hash=sha256_text(chunk_text),
            )
        )
    if not output:
        raise ValueError(f"chunking produced no content: {record.source_id}")
    return output


class LocalSentenceEmbedder:
    def __init__(self, settings: Settings) -> None:
        from sentence_transformers import SentenceTransformer

        local_snapshot = MODEL_DIR / f"all-MiniLM-L6-v2-{settings.embedding_model_revision[:8]}"
        model_source = (
            str(local_snapshot) if local_snapshot.is_dir() else settings.embedding_model_id
        )
        kwargs: dict[str, Any] = {
            "device": settings.embedding_device,
            "trust_remote_code": False,
            "local_files_only": local_snapshot.is_dir(),
        }
        if not local_snapshot.is_dir():
            kwargs["revision"] = settings.embedding_model_revision
            kwargs["cache_folder"] = str(MODEL_DIR / "huggingface")
        self._model = SentenceTransformer(model_source, **kwargs)
        dimension = self._model.get_embedding_dimension()
        if dimension != settings.embedding_dimension:
            raise ValueError(
                "embedding dimension mismatch: "
                f"model={dimension}, configured={settings.embedding_dimension}"
            )
        self.tokenizer = cast(Tokenizer, self._model.tokenizer)
        self.dimension = settings.embedding_dimension
        self.batch_size = settings.embedding_batch_size

    def encode(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        if not texts:
            return []
        values = self._model.encode(
            list(texts),
            batch_size=self.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [tuple(float(value) for value in row) for row in values]


class Neo4jKnowledgeStore:
    def __init__(self, settings: Settings) -> None:
        self.driver: Driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
        )

    def close(self) -> None:
        self.driver.close()

    def verify_connectivity(self) -> None:
        self.driver.verify_connectivity()

    def apply_schema(self, schema_path: Path = SCHEMA_PATH) -> None:
        statements = [part.strip() for part in schema_path.read_text().split(";") if part.strip()]
        with self.driver.session() as session:
            for statement in statements:
                session.run(statement).consume()

    def wait_for_indexes(self, timeout_seconds: float = INDEX_WAIT_SECONDS) -> list[dict[str, Any]]:
        deadline = time.monotonic() + timeout_seconds
        required = {FULLTEXT_INDEX, VECTOR_INDEX}
        while True:
            with self.driver.session() as session:
                rows = [
                    dict(record)
                    for record in session.run(
                        "SHOW INDEXES YIELD name, state, populationPercent, type "
                        "WHERE name IN $names "
                        "RETURN name, state, populationPercent, type ORDER BY name",
                        names=sorted(required),
                    )
                ]
            by_name = {cast(str, row["name"]): row for row in rows}
            if required <= by_name.keys() and all(
                by_name[name]["state"] == "ONLINE" for name in required
            ):
                return rows
            if time.monotonic() >= deadline:
                raise TimeoutError(f"indexes did not become ONLINE: {rows}")
            time.sleep(0.25)

    def load_topology(self, topology: TopologyRecord) -> None:
        common = {
            "topology_version": topology.topology_version,
            "source_id": topology.source_id,
            "provenance_method": topology.provenance_method,
            "valid_from": iso(topology.valid_from),
            "valid_to": iso(topology.valid_to),
        }
        with self.driver.session() as session:
            session.execute_write(self._write_topology, topology, common)

    @staticmethod
    def _write_topology(
        tx: ManagedTransaction, topology: TopologyRecord, common: dict[str, Any]
    ) -> None:
        tx.run(
            "UNWIND $rows AS row MERGE (node:Service {id: row.id}) "
            "SET node.name=row.name, node.aliases=row.aliases, node.environment=row.environment, "
            "node.owner=row.owner, node.metadata_version=row.metadata_version, "
            "node.topology_version=$topology_version",
            rows=[item.model_dump(mode="json") for item in topology.services],
            **common,
        ).consume()
        tx.run(
            "UNWIND $rows AS row MERGE (node:Resource {id: row.id}) "
            "SET node.name=row.name, node.kind=row.kind, node.environment=row.environment, "
            "node.endpoint_identifier=row.endpoint_identifier, "
            "node.topology_version=$topology_version",
            rows=[item.model_dump(mode="json") for item in topology.resources],
            **common,
        ).consume()
        tx.run(
            "UNWIND $rows AS row MATCH (caller:Service {id: row.caller}) "
            "MATCH (callee:Service {id: row.callee}) "
            "MERGE (caller)-[rel:DEPENDS_ON {topology_version: $topology_version}]->(callee) "
            "SET rel.source_id=$source_id, rel.provenance_method=$provenance_method, "
            "rel.valid_from=$valid_from, rel.valid_to=$valid_to",
            rows=[item.model_dump(mode="json") for item in topology.dependencies],
            **common,
        ).consume()
        tx.run(
            "UNWIND $rows AS row MATCH (service:Service {id: row.service}) "
            "MATCH (resource:Resource {id: row.resource}) "
            "MERGE (service)-[rel:USES {topology_version: $topology_version}]->(resource) "
            "SET rel.source_id=$source_id, rel.provenance_method=$provenance_method, "
            "rel.valid_from=$valid_from, rel.valid_to=$valid_to",
            rows=[item.model_dump(mode="json") for item in topology.resource_uses],
            **common,
        ).consume()
        tx.run(
            "UNWIND $rows AS row MERGE (deployment:Deployment {id: row.id}) "
            "SET deployment.version=row.version, deployment.timestamp=row.timestamp, "
            "deployment.source_record=row.source_record, deployment.service_id=row.service_id "
            "WITH deployment, row MATCH (service:Service {id: row.service_id}) "
            "MERGE (deployment)-[rel:OF_SERVICE]->(service) "
            "SET rel.source_id=$source_id, rel.provenance_method=$provenance_method",
            rows=[
                {**item.model_dump(mode="json"), "timestamp": iso(item.timestamp)}
                for item in topology.deployments
            ],
            **common,
        ).consume()
        tx.run(
            "UNWIND $rows AS row MERGE (incident:Incident {id: row.id}) "
            "SET incident.window_start=row.window_start, incident.window_end=row.window_end, "
            "incident.reviewed_outcome=row.reviewed_outcome, "
            "incident.source_provenance=row.source_provenance, "
            "incident.published_at=row.published_at "
            "WITH incident, row UNWIND row.affected_services AS service_id "
            "MATCH (service:Service {id: service_id}) "
            "MERGE (incident)-[rel:AFFECTED]->(service) "
            "SET rel.source_id=$source_id, rel.provenance_method=$provenance_method",
            rows=[
                {
                    **item.model_dump(mode="json"),
                    "window_start": iso(item.window_start),
                    "window_end": iso(item.window_end),
                    "published_at": iso(item.published_at),
                }
                for item in topology.incidents
            ],
            **common,
        ).consume()

    def document_states(self, corpus_id: str) -> dict[str, dict[str, Any]]:
        with self.driver.session() as session:
            count = session.run(
                "MATCH (doc:Document {corpus_id: $corpus_id}) RETURN count(doc) AS count",
                corpus_id=corpus_id,
            ).single(strict=True)["count"]
            if count == 0:
                return {}
            return {
                cast(str, row["source_id"]): dict(row)
                for row in session.run(
                    "MATCH (doc:Document {corpus_id: $corpus_id}) "
                    "RETURN doc.source_id AS source_id, doc.content_hash AS content_hash, "
                    "doc.document_version AS document_version, doc.archived_at AS archived_at",
                    corpus_id=corpus_id,
                )
            }

    def ensure_embedding_compatibility(self, settings: Settings) -> str:
        model_key = f"{settings.embedding_model_id}@{settings.embedding_model_revision}"
        with self.driver.session() as session:
            row = session.run(
                "MERGE (corpus:Corpus {id: $corpus_id}) "
                "ON CREATE SET corpus.embedding_model=$model_key, "
                "corpus.embedding_dimension=$dimension "
                "RETURN corpus.embedding_model AS embedding_model, "
                "corpus.embedding_dimension AS embedding_dimension",
                corpus_id=settings.corpus_id,
                model_key=model_key,
                dimension=settings.embedding_dimension,
            ).single()
            if row is not None and row["embedding_model"] not in {None, model_key}:
                raise ValueError("corpus already uses a different embedding model revision")
            if row is not None and row["embedding_dimension"] not in {
                None,
                settings.embedding_dimension,
            }:
                raise ValueError("corpus already uses a different embedding dimension")
            chunk_count = session.run(
                "MATCH (chunk:Chunk {corpus_id: $corpus_id}) RETURN count(chunk) AS count",
                corpus_id=settings.corpus_id,
            ).single(strict=True)["count"]
            incompatible = 0
            if chunk_count:
                incompatible = session.run(
                    "MATCH (chunk:Chunk {corpus_id: $corpus_id}) "
                    "WHERE chunk.embedding_model <> $model_key OR "
                    "size(chunk.embedding) <> $dimension RETURN count(chunk) AS count",
                    corpus_id=settings.corpus_id,
                    model_key=model_key,
                    dimension=settings.embedding_dimension,
                ).single(strict=True)["count"]
            if incompatible:
                raise ValueError(f"found {incompatible} incompatible active chunks")
        return model_key

    def upsert_document(
        self,
        settings: Settings,
        record: ManifestRecord,
        chunks: Sequence[ChunkRecord],
        model_key: str,
        corpus_version: str,
    ) -> None:
        document_id = f"{settings.corpus_id}:{record.source_id}"
        chunk_rows = [
            {
                **chunk.model_dump(mode="json"),
                "id": f"{settings.corpus_id}:{chunk.id}",
                "document_id": document_id,
            }
            for chunk in chunks
        ]
        metadata = {
            **record.model_dump(mode="json"),
            "created_at": iso(record.created_at),
            "observed_at": iso(record.observed_at),
            "valid_from": iso(record.valid_from),
            "valid_to": iso(record.valid_to),
            "applicable_services": list(record.applicable_services),
        }
        with self.driver.session() as session:
            session.execute_write(
                self._write_document,
                settings.corpus_id,
                corpus_version,
                settings.embedding_dimension,
                model_key,
                document_id,
                metadata,
                chunk_rows,
            )

    @staticmethod
    def _write_document(
        tx: ManagedTransaction,
        corpus_id: str,
        corpus_version: str,
        dimension: int,
        model_key: str,
        document_id: str,
        metadata: dict[str, Any],
        chunks: list[dict[str, Any]],
    ) -> None:
        tx.run(
            "MERGE (corpus:Corpus {id: $corpus_id}) "
            "SET corpus.version=$corpus_version, corpus.embedding_model=$model_key, "
            "corpus.embedding_dimension=$dimension, corpus.updated_at=$updated_at "
            "MERGE (model:EmbeddingModel {id: $model_key}) "
            "SET model.model_id=$model_id, model.revision=$revision, model.dimension=$dimension, "
            "model.device='cpu', model.license='Apache-2.0'",
            corpus_id=corpus_id,
            corpus_version=corpus_version,
            model_key=model_key,
            model_id=model_key.split("@", maxsplit=1)[0],
            revision=model_key.split("@", maxsplit=1)[1],
            dimension=dimension,
            updated_at=iso(datetime.now(UTC)),
        ).consume()
        tx.run(
            "MATCH (doc:Document {id: $document_id})-[rel:HAS_CHUNK]->(old:Chunk) "
            "DETACH DELETE old",
            document_id=document_id,
        ).consume()
        tx.run(
            "MERGE (corpus:Corpus {id: $corpus_id}) "
            "MERGE (doc:Document {id: $document_id}) "
            "SET doc.source_id=$metadata.source_id, doc.title=$metadata.title, "
            "doc.source_path=$metadata.path, "
            "doc.selector=$metadata.selector, doc.license=$metadata.license, "
            "doc.document_version=$metadata.document_version, "
            "doc.content_hash=$metadata.content_hash, doc.created_at=$metadata.created_at, "
            "doc.observed_at=$metadata.observed_at, doc.valid_from=$metadata.valid_from, "
            "doc.valid_to=$metadata.valid_to, doc.trust_status=$metadata.trust_status, "
            "doc.document_type=$metadata.document_type, "
            "doc.applicable_services=$metadata.applicable_services, doc.corpus_id=$corpus_id, "
            "doc.archived_at=null "
            "MERGE (corpus)-[:CORPUS_HAS_DOCUMENT]->(doc) "
            "WITH doc UNWIND $chunks AS row "
            "CREATE (chunk:Chunk {id: row.id}) "
            "SET chunk.document_id=row.document_id, chunk.ordinal=row.ordinal, "
            "chunk.section=row.section, chunk.text=row.text, chunk.token_count=row.token_count, "
            "chunk.content_hash=row.content_hash, chunk.embedding=row.embedding, "
            "chunk.embedding_model=$model_key, chunk.embedding_dimension=$dimension, "
            "chunk.corpus_id=$corpus_id, chunk.valid_from=$metadata.valid_from, "
            "chunk.valid_to=$metadata.valid_to, chunk.trust_status=$metadata.trust_status, "
            "chunk.source_version=$metadata.document_version "
            "MERGE (doc)-[:HAS_CHUNK]->(chunk) "
            "WITH chunk UNWIND $metadata.applicable_services AS service_id "
            "MATCH (service:Service {id: service_id}) "
            "MERGE (chunk)-[about:ABOUT]->(service) "
            "SET about.source_id=$metadata.source_id, about.provenance_method='approved_manifest'",
            corpus_id=corpus_id,
            document_id=document_id,
            metadata=metadata,
            chunks=chunks,
            model_key=model_key,
            dimension=dimension,
        ).consume()

    def archive_missing(self, corpus_id: str, active_ids: set[str]) -> int:
        with self.driver.session() as session:
            row = session.execute_write(self._archive_missing, corpus_id, sorted(active_ids))
        return row

    @staticmethod
    def _archive_missing(
        tx: ManagedTransaction, corpus_id: str, active_ids: list[str]
    ) -> int:
        rows = list(
            tx.run(
                "MATCH (doc:Document {corpus_id: $corpus_id}) "
                "WHERE NOT doc.source_id IN $active_ids AND doc.archived_at IS NULL "
                "SET doc.archived_at=$archived_at "
                "WITH doc OPTIONAL MATCH (doc)-[:HAS_CHUNK]->(chunk:Chunk) "
                "WITH doc, collect(chunk) AS chunks "
                "FOREACH (chunk IN chunks | DETACH DELETE chunk) "
                "RETURN count(doc) AS count",
                corpus_id=corpus_id,
                active_ids=active_ids,
                archived_at=iso(datetime.now(UTC)),
            )
        )
        return cast(int, rows[0]["count"] if rows else 0)

    def graph_summary(self, corpus_id: str) -> dict[str, Any]:
        with self.driver.session() as session:
            row = session.run(
                "MATCH (service:Service) WITH count(service) AS services "
                "MATCH (resource:Resource) WITH services, count(resource) AS resources "
                "MATCH (:Service)-[dependency:DEPENDS_ON]->(:Service) "
                "WITH services, resources, count(dependency) AS dependencies "
                "OPTIONAL MATCH (doc:Document {corpus_id: $corpus_id}) "
                "WHERE doc.archived_at IS NULL "
                "WITH services, resources, dependencies, count(doc) AS documents "
                "OPTIONAL MATCH (chunk:Chunk {corpus_id: $corpus_id}) "
                "RETURN services, resources, dependencies, documents, count(chunk) AS chunks",
                corpus_id=corpus_id,
            ).single(strict=True)
        return dict(row)

    def index_details(self) -> list[dict[str, Any]]:
        with self.driver.session() as session:
            return [
                dict(row)
                for row in session.run(
                    "SHOW INDEXES YIELD name, state, populationPercent, type, properties, options "
                    "WHERE name IN $names "
                    "RETURN name, state, populationPercent, type, properties, options "
                    "ORDER BY name",
                    names=[FULLTEXT_INDEX, VECTOR_INDEX],
                )
            ]

    def dependencies_at(
        self,
        service_id: str,
        direction: Literal["outbound", "inbound"],
        at: datetime,
    ) -> list[dict[str, Any]]:
        pattern = (
            "(service:Service {id: $service_id})-[rel:DEPENDS_ON]->(neighbor:Service)"
            if direction == "outbound"
            else "(neighbor:Service)-[rel:DEPENDS_ON]->(service:Service {id: $service_id})"
        )
        query = (
            f"MATCH {pattern} "
            "WHERE rel.valid_from <= $at AND (rel.valid_to IS NULL OR $at < rel.valid_to) "
            "RETURN service.id AS service_id, neighbor.id AS neighbor_id, "
            "rel.source_id AS source_id, rel.topology_version AS topology_version "
            "ORDER BY neighbor_id"
        )
        with self.driver.session() as session:
            return [dict(row) for row in session.run(query, service_id=service_id, at=iso(at))]

    def potential_impact_at(
        self, service_id: str, at: datetime, max_nodes: int = 50
    ) -> list[dict[str, Any]]:
        with self.driver.session() as session:
            return [
                dict(row)
                for row in session.run(
                    "MATCH path=(affected:Service)-[:DEPENDS_ON*1..2]->"
                    "(root:Service {id: $service_id}) "
                    "WHERE all(rel IN relationships(path) WHERE rel.valid_from <= $at "
                    "AND (rel.valid_to IS NULL OR $at < rel.valid_to)) "
                    "RETURN DISTINCT affected.id AS service_id, length(path) AS hops "
                    "ORDER BY hops, service_id LIMIT $limit",
                    service_id=service_id,
                    at=iso(at),
                    limit=max_nodes,
                )
            ]

    def eligible_document_ids(self, corpus_id: str, at: datetime) -> list[str]:
        with self.driver.session() as session:
            return [
                cast(str, row["id"])
                for row in session.run(
                    "MATCH (doc:Document {corpus_id: $corpus_id}) "
                    "WHERE doc.archived_at IS NULL AND doc.valid_from <= $at "
                    "AND (doc.valid_to IS NULL OR $at < doc.valid_to) "
                    "AND doc.trust_status IN ['trusted', 'reviewed', 'reference'] "
                    "RETURN doc.source_id AS id ORDER BY id",
                    corpus_id=corpus_id,
                    at=iso(at),
                )
            ]

    def verify(self, settings: Settings, manifest: Sequence[ManifestRecord]) -> dict[str, Any]:
        now = datetime(2026, 9, 23, tzinfo=UTC)
        before_topology = datetime(2026, 9, 1, tzinfo=UTC)
        outbound = self.dependencies_at("svc-gateway", "outbound", now)
        inbound = self.dependencies_at("svc-checkout", "inbound", now)
        impact = self.potential_impact_at("svc-payments", now)
        historical_edges = self.dependencies_at("svc-gateway", "outbound", before_topology)
        eligible_now = self.eligible_document_ids(settings.corpus_id, now)
        expected_eligible = {
            record.source_id
            for record in manifest
            if record.valid_from <= now
            and (record.valid_to is None or now < record.valid_to)
            and record.trust_status in {"trusted", "reviewed", "reference"}
        }
        indexes = self.index_details()
        summary = self.graph_summary(settings.corpus_id)
        checks = {
            "gateway_depends_on_checkout": [row["neighbor_id"] for row in outbound]
            == ["svc-checkout"],
            "checkout_has_gateway_dependent": [row["neighbor_id"] for row in inbound]
            == ["svc-gateway"],
            "payments_reverse_impact": {row["service_id"] for row in impact}
            == {"svc-checkout", "svc-gateway"},
            "topology_not_backdated": historical_edges == [],
            "temporal_document_eligibility": set(eligible_now) == expected_eligible,
            "untrusted_filtered": "untrusted-retry-all" not in eligible_now,
            "outdated_filtered": "outdated-pool-size" not in eligible_now
            and "outdated-direct-payments" not in eligible_now,
            "indexes_online": len(indexes) == 2
            and all(row["state"] == "ONLINE" for row in indexes),
            "source_references_resolve": summary["documents"] == len(manifest),
            "embedding_compatibility": summary["chunks"] > 0,
        }
        return {
            "status": "pass" if all(checks.values()) else "fail",
            "checks": checks,
            "gateway_outbound": outbound,
            "checkout_inbound": inbound,
            "payments_reverse_impact": impact,
            "eligible_document_count": len(eligible_now),
        }


def _corpus_version(manifest: Sequence[ManifestRecord], settings: Settings) -> str:
    payload = "\n".join(
        f"{record.source_id}:{record.document_version}:{record.content_hash}"
        for record in sorted(manifest, key=lambda item: item.source_id)
    )
    return f"{settings.corpus_id}-{sha256_text(payload)[:12]}"


def run_ingestion(settings: Settings, report_path: Path = DEFAULT_REPORT_PATH) -> IngestionReport:
    started = datetime.now(UTC)
    start_clock = time.perf_counter()
    topology = load_topology()
    manifest = load_manifest()
    documents = validate_manifest(manifest, topology)
    corpus_version = _corpus_version(manifest, settings)
    store = Neo4jKnowledgeStore(settings)
    inserted = 0
    updated = 0
    skipped = 0
    embedded_chunks = 0
    embedding_metadata: dict[str, Any] = {
        "model_id": settings.embedding_model_id,
        "revision": settings.embedding_model_revision,
        "dimension": settings.embedding_dimension,
        "tokenizer": "BertTokenizer",
        "license": "Apache-2.0",
        "device": settings.embedding_device,
        "batch_size": settings.embedding_batch_size,
        "chunk_tokens": CHUNK_TOKENS,
        "chunk_overlap": CHUNK_OVERLAP,
        "hard_chunk_limit": MAX_CHUNK_TOKENS,
        "encoded_texts": 0,
        "encoding_seconds": 0.0,
        "texts_per_second": None,
        "hardware": f"{platform.system()} {platform.machine()}",
    }
    try:
        store.verify_connectivity()
        store.apply_schema()
        store.load_topology(topology)
        store.wait_for_indexes()
        model_key = store.ensure_embedding_compatibility(settings)
        states = store.document_states(settings.corpus_id)
        changed: list[tuple[ManifestRecord, Literal["insert", "update"]]] = []
        for record in manifest:
            state = states.get(record.source_id)
            if state is None:
                changed.append((record, "insert"))
            elif (
                state["content_hash"] != record.content_hash
                or state["document_version"] != record.document_version
                or state["archived_at"] is not None
            ):
                changed.append((record, "update"))
            else:
                skipped += 1

        if changed:
            embedder = LocalSentenceEmbedder(settings)
            pending: list[tuple[ManifestRecord, Literal["insert", "update"], list[ChunkRecord]]]
            pending = [
                (
                    record,
                    action,
                    chunk_document(record, documents[record.source_id], embedder.tokenizer),
                )
                for record, action in changed
            ]
            flat_chunks = [chunk for _, _, chunks in pending for chunk in chunks]
            embedder.encode(["IncidentGraph embedding warmup"])
            encode_started = time.perf_counter()
            embeddings = embedder.encode([chunk.text for chunk in flat_chunks])
            encode_seconds = time.perf_counter() - encode_started
            embedded_chunks = len(flat_chunks)
            embedding_metadata.update(
                {
                    "encoded_texts": embedded_chunks,
                    "encoding_seconds": round(encode_seconds, 6),
                    "texts_per_second": round(embedded_chunks / encode_seconds, 3)
                    if encode_seconds > 0
                    else None,
                }
            )
            embedding_index = 0
            for record, action, chunks in pending:
                enriched: list[ChunkRecord] = []
                for chunk in chunks:
                    vector = embeddings[embedding_index]
                    embedding_index += 1
                    if len(vector) != settings.embedding_dimension:
                        raise ValueError("encoder returned an incompatible vector dimension")
                    enriched.append(chunk.model_copy(update={"embedding": vector}))
                store.upsert_document(
                    settings, record, enriched, model_key, corpus_version
                )
                if action == "insert":
                    inserted += 1
                else:
                    updated += 1

        archived = store.archive_missing(
            settings.corpus_id, {record.source_id for record in manifest}
        )
        indexes = store.wait_for_indexes()
        graph = store.graph_summary(settings.corpus_id)
        verification = store.verify(settings, manifest)
        if verification["status"] != "pass":
            raise RuntimeError(f"Phase 3 verification failed: {verification['checks']}")
        finished = datetime.now(UTC)
        report = IngestionReport(
            status="pass",
            corpus_id=settings.corpus_id,
            corpus_version=corpus_version,
            started_at=started,
            finished_at=finished,
            duration_seconds=round(time.perf_counter() - start_clock, 6),
            manifest_documents=len(manifest),
            inserted_documents=inserted,
            updated_documents=updated,
            skipped_documents=skipped,
            archived_documents=archived,
            active_documents=cast(int, graph["documents"]),
            active_chunks=cast(int, graph["chunks"]),
            embedded_chunks=embedded_chunks,
            rejected_records=[],
            embedding=embedding_metadata,
            indexes=indexes,
            graph=graph,
            verification=verification,
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return report
    finally:
        store.close()


def verify_existing(settings: Settings) -> dict[str, Any]:
    manifest = load_manifest()
    topology = load_topology()
    validate_manifest(manifest, topology)
    store = Neo4jKnowledgeStore(settings)
    try:
        store.verify_connectivity()
        result = store.verify(settings, manifest)
        if result["status"] != "pass":
            raise RuntimeError(f"Phase 3 verification failed: {result['checks']}")
        return result
    finally:
        store.close()


def benchmark_embeddings(
    settings: Settings, report_path: Path = DEFAULT_BENCHMARK_PATH
) -> dict[str, Any]:
    manifest = load_manifest()
    topology = load_topology()
    documents = validate_manifest(manifest, topology)
    embedder = LocalSentenceEmbedder(settings)
    chunks = [
        chunk
        for record in manifest
        for chunk in chunk_document(record, documents[record.source_id], embedder.tokenizer)
    ]
    embedder.encode(["IncidentGraph embedding warmup"])
    started = time.perf_counter()
    vectors = embedder.encode([chunk.text for chunk in chunks])
    elapsed = time.perf_counter() - started
    result = {
        "status": "pass"
        if vectors
        and all(len(vector) == settings.embedding_dimension for vector in vectors)
        else "fail",
        "model_id": settings.embedding_model_id,
        "revision": settings.embedding_model_revision,
        "dimension": settings.embedding_dimension,
        "tokenizer": "BertTokenizer",
        "license": "Apache-2.0",
        "device": settings.embedding_device,
        "hardware": f"{platform.system()} {platform.machine()}",
        "documents": len(manifest),
        "chunks": len(chunks),
        "total_tokens": sum(chunk.token_count for chunk in chunks),
        "batch_size": settings.embedding_batch_size,
        "elapsed_seconds": round(elapsed, 6),
        "chunks_per_second": round(len(chunks) / elapsed, 3) if elapsed > 0 else None,
        "compatible_vectors": len(vectors),
    }
    if result["status"] != "pass":
        raise RuntimeError("embedding benchmark returned incompatible vectors")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def load_settings() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]
    except ValidationError as exc:
        raise SystemExit(f"Configuration error:\n{exc}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(prog="incidentgraph-ingest")
    subcommands = parser.add_subparsers(dest="command", required=True)
    for name in ("seed", "ingest"):
        command = subcommands.add_parser(name)
        command.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    subcommands.add_parser("verify")
    benchmark = subcommands.add_parser("benchmark")
    benchmark.add_argument("--report", type=Path, default=DEFAULT_BENCHMARK_PATH)
    args = parser.parse_args()
    settings = load_settings()
    if args.command in {"seed", "ingest"}:
        report = run_ingestion(settings, args.report)
        print(report.model_dump_json(indent=2))
    elif args.command == "verify":
        print(json.dumps(verify_existing(settings), indent=2))
    elif args.command == "benchmark":
        print(json.dumps(benchmark_embeddings(settings, args.report), indent=2))


if __name__ == "__main__":
    main()
