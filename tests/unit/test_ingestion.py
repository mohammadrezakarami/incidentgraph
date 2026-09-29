from __future__ import annotations

from pathlib import Path

import pytest

from incidentgraph.ingestion import (
    CHUNK_OVERLAP,
    CHUNK_TOKENS,
    MAX_CHUNK_TOKENS,
    ManifestRecord,
    chunk_document,
    load_manifest,
    load_topology,
    read_document,
    validate_manifest,
)


class WordTokenizer:
    def __init__(self) -> None:
        self._words: list[str] = []

    def encode(self, text: str, *, add_special_tokens: bool = False) -> list[int]:
        del add_special_tokens
        start = len(self._words)
        words = text.split()
        self._words.extend(words)
        return list(range(start, start + len(words)))

    def decode(self, token_ids: list[int], *, skip_special_tokens: bool = True) -> str:
        del skip_special_tokens
        return " ".join(self._words[token_id] for token_id in token_ids)


def test_curated_manifest_resolves_hashes_and_services() -> None:
    manifest = load_manifest()
    topology = load_topology()
    documents = validate_manifest(manifest, topology)

    assert len(manifest) == 37
    assert len(documents) == 37
    assert {record.trust_status for record in manifest} == {
        "trusted",
        "reviewed",
        "reference",
        "outdated",
        "untrusted",
    }
    assert {service.id for service in topology.services} == {
        "svc-gateway",
        "svc-checkout",
        "svc-payments",
    }


def test_topology_dependency_direction_is_caller_to_callee() -> None:
    topology = load_topology()
    edges = {(edge.caller, edge.callee) for edge in topology.dependencies}

    assert edges == {
        ("svc-gateway", "svc-checkout"),
        ("svc-checkout", "svc-payments"),
    }


def test_chunking_has_hard_bound_and_overlap() -> None:
    tokenizer = WordTokenizer()
    record = load_manifest()[0]
    text = " ".join(f"token-{number}" for number in range(1_300))

    chunks = chunk_document(record, text, tokenizer)

    assert len(chunks) == 3
    assert all(chunk.token_count <= MAX_CHUNK_TOKENS for chunk in chunks)
    assert chunks[0].token_count == CHUNK_TOKENS
    assert chunks[1].token_count == CHUNK_TOKENS
    first_words = chunks[0].text.split()
    second_words = chunks[1].text.split()
    assert first_words[-CHUNK_OVERLAP:] == second_words[:CHUNK_OVERLAP]


def test_chunk_ids_are_stable_and_change_with_content() -> None:
    tokenizer = WordTokenizer()
    record = load_manifest()[0]
    first = chunk_document(record, "# Heading\n\nStable content for chunk identity.", tokenizer)
    second = chunk_document(record, "# Heading\n\nStable content for chunk identity.", tokenizer)
    changed = chunk_document(record, "# Heading\n\nChanged content for chunk identity.", tokenizer)

    assert [chunk.id for chunk in first] == [chunk.id for chunk in second]
    assert [chunk.id for chunk in first] != [chunk.id for chunk in changed]


def test_manifest_rejects_path_traversal(tmp_path: Path) -> None:
    record = load_manifest()[0].model_copy(update={"path": "../outside.txt", "selector": None})
    (tmp_path.parent / "outside.txt").write_text("x" * 100, encoding="utf-8")

    with pytest.raises(ValueError, match="leaves corpus root"):
        read_document(record, tmp_path)


def test_manifest_rejects_invalid_interval() -> None:
    payload = load_manifest()[0].model_dump(mode="json")
    payload["valid_to"] = payload["valid_from"]

    with pytest.raises(ValueError, match="valid_to must be after valid_from"):
        ManifestRecord.model_validate(payload)
