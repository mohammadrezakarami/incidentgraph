# PHASE 3 REPORT — Knowledge Graph and Ingestion

Status: PASS

Date: 2026-09-23

Roadmap position: Phase 3 of 11 delivery phases is complete. Counting discovery Phase 0, 4 of 12 gated phases are complete and 8 remain.

## 1. Objective and result

Phase 3 was intended to create the versioned operational graph and trustworthy document-ingestion foundation required by later retrieval work. It now provides reviewed graph constraints and topology, a 37-document curated corpus, structure-aware bounded chunking, immutable local embedding-model metadata, incremental Neo4j upserts, temporal eligibility, full-text/vector indexes, and executable gate verification.

The phase passes. The active graph contains three services, three resources, two caller-to-callee dependency edges, six resource-use edges, three deployment records, and three reviewed synthetic development incidents. The corpus contains 37 active documents and 37 active chunks. At the 2026-09-23 cutoff, 34 documents are eligible; two expired documents and one untrusted document are excluded. Both search indexes are `ONLINE` at 100 percent population.

No external dataset, hosted embedding API, paid call, GPU, or Colab run was used. The only model download was the pinned 91.6 MB public MiniLM snapshot, cached under ignored `models/`.

## 2. Implemented changes

- `config/graph_schema.cypher` defines stable-ID uniqueness constraints, range indexes, the chunk full-text index, and the 384-dimensional cosine vector index.
- `config/topology.json` is the reviewed declarative source for services, resources, caller-to-callee dependencies, resource uses, deployments, reviewed incidents, provenance, and validity.
- `data/corpus/documents.json` stores 37 useful project-authored laboratory documents in one compact bundle.
- `data/corpus/manifest.jsonl` records source IDs, selectors, licenses, SHA-256 hashes, versions, timestamps, services, trust states, document types, and validity intervals.
- `data/corpus/README.md` documents provenance, temporal filtering, update behavior, removal policy, and commands.
- `src/incidentgraph/ingestion.py` implements manifest/topology validation, safe local parsing, normalization, structural chunking, local embedding, graph loading, incremental upserts, archival, index readiness, time-aware queries, verification, reporting, and CLI commands.
- `src/incidentgraph/config.py` validates embedding model, immutable revision, dimension, CPU device, batch size, and corpus ID.
- `tests/unit/test_ingestion.py` and `tests/integration/test_phase3_graph.py` cover manifest integrity, path confinement, chunk bounds/overlap, stable IDs, graph direction, idempotency, partial-run resume, changed-content replacement, and model incompatibility.
- `artifacts/ingestion/phase3-latest.json` and `artifacts/ingestion/embedding-benchmark.json` retain measured run evidence.
- `Makefile`, `.env.example`, `pyproject.toml`, and `uv.lock` expose and pin the working operational interface.

## 3. Decisions and tradeoffs

The authoritative topology is declarative and reviewed. No LLM extraction is allowed to silently define trusted dependency edges. `DEPENDS_ON` points from caller to callee, while potential-impact queries traverse the reverse path.

The corpus uses one compact JSON bundle plus one JSONL manifest rather than dozens of nested directories. Documents remain independently addressable through stable source IDs and selectors. Document and chunk node IDs are namespaced by corpus ID so integration and future corpus snapshots cannot collide.

The embedding model is `sentence-transformers/all-MiniLM-L6-v2` at full revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, Apache-2.0, BERT tokenizer, 384 dimensions, CPU, and batch size 16. The model card identifies the 384-dimensional semantic-search use case: <https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2>. The vector design follows the pinned Neo4j version's documented Community-compatible list embeddings and dimension checks: <https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/vector-indexes/>.

Chunking targets 500 tokens with 75-token overlap and enforces a 600-token hard limit. The current curated documents are intentionally concise, so each becomes one structural chunk rather than being padded or combined across source boundaries.

Unchanged documents are skipped before loading the model. Changed documents replace their old chunks inside one Neo4j transaction. Removed documents retain archived metadata but lose searchable chunks. This favors provenance and safe reruns over destructive deletion.

The first live seed exposed two verifier defects: the archive check compared namespaced document IDs with source IDs, and eligibility returned namespaced IDs instead of source IDs. Both runs correctly failed the gate. The implementation was corrected, data was restored by the normal idempotent ingest path, and only the passing evidence is reported as the phase result.

## 4. Verification evidence

| Command | Result | Evidence |
|---|---|---|
| `make lint` | PASS | Ruff reported no issues |
| `make typecheck` | PASS | Strict mypy reported no issues in 15 source files |
| `make test` | PASS | 22 unit tests passed; 4 integration tests were intentionally deselected |
| `make test-integration` | PASS | 1 real PostgreSQL durability test passed |
| `make test-lab-integration` | PASS | 2 live transaction/Prometheus/capture tests passed |
| `make test-graph-integration` | PASS | 1 real Neo4j/model test passed; no mocks |
| `make verify-captures` | PASS | All 17 Phase 2 capture contracts still pass |
| `make ingest` | PASS | 37 unchanged documents skipped; 0 re-embedded; duration 0.215235 seconds |
| `make verify-ingestion` | PASS | Direction, impact, time, trust, indexes, references, and compatibility passed |
| `make benchmark-embeddings` | PASS | 37 chunks / 3,338 tokens encoded in 0.14048 seconds, 263.383 chunks/second |
| `make coverage` | FAIL / retained later-core gate | 38.71 percent versus unchanged 85 percent threshold |

The graph integration test creates an isolated namespaced corpus, ingests all 37 sources, confirms a second run embeds nothing, removes one document to simulate partial interruption, confirms only that document is restored on resume, changes its content and confirms prior chunk IDs disappear, rejects a 768-dimensional mismatch, and deletes the temporary test corpus. It uses the real Neo4j service and real local MiniLM model.

The CPU number is a small warm-cache local measurement, not a capacity or cross-machine benchmark. The model load is excluded from the encode interval and remains visible separately to users.

## 5. Acceptance checklist

| Criterion | Result |
|---|---|
| Stable graph constraints and provenance-aware topology | PASS |
| Correct caller-to-callee graph direction | PASS |
| Reverse potential-impact traversal | PASS |
| Historical/time-aware topology queries | PASS |
| 30–50 useful curated documents with manifest provenance | PASS — 37 |
| Structure-aware bounded chunking | PASS |
| Pinned local embedding model and dimension validation | PASS |
| Full-text and vector indexes ready | PASS |
| Repeated ingestion is idempotent | PASS |
| Changed content has no stale duplicate chunks | PASS |
| Interrupted partial ingestion resumes safely | PASS |
| Source references and hashes resolve | PASS |
| Removed-document archival policy documented | PASS |

## 6. How I can try it

Prerequisites are the existing project environment, `.env`, Docker Desktop, and the local services:

```bash
make up
make seed
make ingest
make verify-ingestion
make benchmark-embeddings
make test-graph-integration
```

`make seed` and `make ingest` are safe incremental operations. On an unchanged corpus they report all 37 documents as skipped and perform no embedding work. The first uncached model fetch is approximately 92 MB. `make down` stops services without deleting Neo4j data or other named volumes.

## 7. Limitations and risks

- This is a project-authored laboratory corpus, not evidence from production incidents.
- The current 37 short documents yield 37 chunks. Phase 4 must measure whether they support useful ranking; index readiness is not retrieval quality.
- Phase 2 captures predate this corpus and cannot be used as final as-of cases without recapture after the corpus baseline.
- The Python environment occupies approximately 1.0 GB because the CPU sentence-transformers runtime includes PyTorch; the cached model directory is approximately 87 MB on disk.
- Neo4j Community has coarser authorization than Enterprise; the later agent must use narrow reviewed read templates.
- Retrieval, evidence objects, an investigator, and real LLM calls are not implemented yet.
- The retained global coverage target is 85 percent; current unit-only global coverage is 38.71 percent.

## 8. What I should understand

The important concept is that vector similarity and graph truth have different jobs. Embeddings help find semantically related text. Reviewed graph edges express known operational structure and time validity. Neither establishes causality; later retrieval will combine them while retaining the source and path that introduced each result.

**Interview question: Why not let an LLM discover the service topology?**  The lab topology is an authorization- and causality-sensitive source of truth. A model may propose candidate relations, but trusted edges require declarative configuration, endpoint validation, provenance, and review so hallucinations cannot become operational facts.

**Interview question: How is incremental ingestion made safe?**  The manifest hash and version identify changed content. Unchanged records skip model loading. Each changed document replaces its chunks in one database transaction, IDs are deterministic and corpus-namespaced, removed sources are archived, and integration tests simulate partial state and rerun recovery.

## 9. Next phase

Phase 4 will implement vector-only, hybrid, and graph-enhanced hybrid retrieval behind one bounded interface. It will add annotated development questions, rank-fusion diagnostics, provenance paths, temporal/context budgets, and executable retrieval metrics on the same corpus snapshot.

Phase 4 requires explicit user approval. It needs no paid model call; the local embedding model is sufficient for retrieval evaluation.

## 10. Resume state

- Branch: `main`.
- Phase 3 implementation commit: `200a655`.
- Runtime: Docker services remain available; Neo4j contains the passing canonical corpus.
- Corpus version: `incidentgraph-lab-corpus-v1-466b7569b585`.
- Active graph content: 3 services, 3 resources, 2 dependency edges, 37 documents, 37 chunks.
- Indexes: `chunk_text_fulltext` and `chunk_embedding_vector`, both `ONLINE`.
- Local model cache: ignored `models/all-MiniLM-L6-v2-1110a243`.
- Exact next action: wait for explicit Phase 4 approval, then define the common retrieval contract and development question manifest before implementing any variant.

Awaiting approval to begin Phase 4.
