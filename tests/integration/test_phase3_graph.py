from __future__ import annotations

import os
from pathlib import Path

import pytest

from incidentgraph.config import Settings
from incidentgraph.ingestion import (
    LocalSentenceEmbedder,
    Neo4jKnowledgeStore,
    chunk_document,
    load_manifest,
    run_ingestion,
)


@pytest.mark.integration
@pytest.mark.graph_integration
@pytest.mark.skipif(
    os.getenv("RUN_GRAPH_INTEGRATION") != "1",
    reason="real Neo4j and local embedding model not enabled",
)
def test_incremental_ingestion_is_idempotent_and_replaces_changed_chunks(
    tmp_path: Path,
) -> None:
    base = Settings()  # type: ignore[call-arg]
    settings = base.model_copy(update={"corpus_id": f"{base.corpus_id}-integration"})
    store = Neo4jKnowledgeStore(settings)
    try:
        with store.driver.session() as session:
            session.run(
                "MATCH (corpus:Corpus {id: $corpus_id}) "
                "OPTIONAL MATCH (corpus)-[:CORPUS_HAS_DOCUMENT]->(doc:Document) "
                "OPTIONAL MATCH (doc)-[:HAS_CHUNK]->(chunk:Chunk) "
                "DETACH DELETE chunk, doc, corpus",
                corpus_id=settings.corpus_id,
            ).consume()
    finally:
        store.close()

    try:
        first = run_ingestion(settings, tmp_path / "first.json")
        second = run_ingestion(settings, tmp_path / "second.json")

        assert first.inserted_documents == 37
        assert first.embedded_chunks > 0
        assert second.skipped_documents == 37
        assert second.embedded_chunks == 0
        assert second.verification["status"] == "pass"

        record = load_manifest()[0]
        store = Neo4jKnowledgeStore(settings)
        try:
            with store.driver.session() as session:
                session.run(
                    "MATCH (doc:Document {source_id: $id, corpus_id: $corpus_id}) "
                    "OPTIONAL MATCH (doc)-[:HAS_CHUNK]->(chunk:Chunk) "
                    "DETACH DELETE chunk, doc",
                    id=record.source_id,
                    corpus_id=settings.corpus_id,
                ).consume()
        finally:
            store.close()
        resumed = run_ingestion(settings, tmp_path / "resumed.json")
        assert resumed.inserted_documents == 1
        assert resumed.skipped_documents == 36
        assert resumed.active_documents == 37
        assert resumed.active_chunks == 37

        store = Neo4jKnowledgeStore(settings)
        try:
            incompatible = settings.model_copy(update={"embedding_dimension": 768})
            with pytest.raises(ValueError, match="different embedding dimension"):
                store.ensure_embedding_compatibility(incompatible)
        finally:
            store.close()

        changed_record = record.model_copy(
            update={
                "document_version": "1.0.1-test",
                "content_hash": "0" * 64,
            }
        )
        changed_text = "# Test Update\n\nThis isolated integration update replaces prior chunks."
        embedder = LocalSentenceEmbedder(settings)
        changed_chunks = chunk_document(changed_record, changed_text, embedder.tokenizer)
        vectors = embedder.encode([chunk.text for chunk in changed_chunks])
        changed_chunks = [
            chunk.model_copy(update={"embedding": vectors[index]})
            for index, chunk in enumerate(changed_chunks)
        ]
        model_key = f"{settings.embedding_model_id}@{settings.embedding_model_revision}"

        store = Neo4jKnowledgeStore(settings)
        try:
            with store.driver.session() as session:
                before = {
                    row["id"]
                    for row in session.run(
                        "MATCH (:Document {source_id: $id, corpus_id: $corpus_id})"
                        "-[:HAS_CHUNK]->(chunk:Chunk) "
                        "RETURN chunk.id AS id",
                        id=record.source_id,
                        corpus_id=settings.corpus_id,
                    )
                }
            store.upsert_document(
                settings,
                changed_record,
                changed_chunks,
                model_key,
                first.corpus_version,
            )
            with store.driver.session() as session:
                after = {
                    row["id"]
                    for row in session.run(
                        "MATCH (:Document {source_id: $id, corpus_id: $corpus_id})"
                        "-[:HAS_CHUNK]->(chunk:Chunk) "
                        "RETURN chunk.id AS id",
                        id=record.source_id,
                        corpus_id=settings.corpus_id,
                    )
                }
            assert before
            assert after
            assert before.isdisjoint(after)
            assert len(after) == len(changed_chunks)
        finally:
            store.close()
    finally:
        store = Neo4jKnowledgeStore(settings)
        try:
            with store.driver.session() as session:
                session.run(
                    "MATCH (corpus:Corpus {id: $corpus_id}) "
                    "OPTIONAL MATCH (corpus)-[:CORPUS_HAS_DOCUMENT]->(doc:Document) "
                    "OPTIONAL MATCH (doc)-[:HAS_CHUNK]->(chunk:Chunk) "
                    "DETACH DELETE chunk, doc, corpus",
                    corpus_id=settings.corpus_id,
                ).consume()
        finally:
            store.close()
