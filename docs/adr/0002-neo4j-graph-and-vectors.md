# ADR-0002: Neo4j for Operational Graph and Document Retrieval Indexes

Status: Accepted

Date: 2026-09-22

## Context

The project needs versioned service relationships, document-to-service provenance, vector similarity, full-text retrieval, and bounded graph expansion. Adding a second vector database would increase operational and consistency cost before evidence shows a benefit.

## Decision

Use Neo4j Community Edition as the local default for service/resource/deployment/document relationships and document chunk vector/full-text indexes. Use application-owned, parameterized query templates through the official Python driver. Neo4j GraphRAG primitives may be used where they fit the required retrieval contract, but they will not become a second orchestrator.

## Consequences

- One versioned store serves topology-aware retrieval.
- Every graph-expanded item can retain its provenance path.
- Community Edition authorization limits require a narrow application adapter, isolated credentials, loopback/internal networking, and documented residual risk.
- Raw metrics and logs remain outside Neo4j.
- A second vector store requires a measured future ADR.
