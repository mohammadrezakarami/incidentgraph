# IncidentGraph Lab Corpus v1

This directory contains the curated Phase 3 corpus for the controlled IncidentGraph lab.
It is project-authored laboratory documentation, not production incident data.

## Layout

- `documents.json` contains 37 useful documents in one compact source bundle.
- `manifest.jsonl` is the authoritative provenance manifest. Every line records the stable
  source ID, local path and selector, license, SHA-256 content hash, version, timestamps,
  applicable service IDs, trust status, document type, and validity interval.

The bundle includes service/API documentation, runbooks, configuration notes, short
link-oriented summaries of official references, reviewed synthetic development incidents,
and explicit outdated/untrusted negative controls. It does not contain Phase 2 evaluator
labels, held-out diagnoses, real customer data, or private documents.

## Version and time policy

`incidentgraph-lab-corpus-v1` is the logical corpus ID. The ingestion command derives an
immutable snapshot version from the sorted manifest source IDs, document versions, and
content hashes. Retrieval must enforce `valid_from <= cutoff < valid_to` when `valid_to`
exists and must exclude untrusted material from normal evidence.

Changing a document requires a new content hash and document version. Ingestion atomically
replaces that document's chunks. Unchanged content is not re-embedded. Documents removed
from the manifest are retained as archived metadata while their searchable chunks are
deleted. Older corpus snapshots should be exported before an intentional version migration
when exact historical replay is required.

## Commands

```bash
make seed
make ingest
make verify-ingestion
make benchmark-embeddings
```

The model cache is project-local under ignored `models/`. The pinned model is
`sentence-transformers/all-MiniLM-L6-v2` at revision
`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, using 384-dimensional normalized vectors on
CPU. No hosted embedding API is used.
