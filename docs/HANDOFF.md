# IncidentGraph Handoff

Last updated: 2026-09-23

## Current phase

Phase 0 through Phase 4 are complete and passed. Phase 5 is not approved yet.

Roadmap position: Phase 4 of 11 delivery phases is complete; including Phase 0, 5 of 12 gates are complete and 7 remain.

## Last verified command

Executable verification of the Phase 4 retrieval contract:

```text
make verify-retrieval
make test-retrieval-integration
make evaluate-retrieval-dev
```

Result: the 20/20 grouped split and held-out SHA-256 seal pass; both real retrieval integration tests pass; graph retrieval scores Recall@5 0.908, MRR@5 1.000, and nDCG@5 0.957 on development. Held-out was not evaluated. The required graph-only case traverses `svc-gateway -> svc-checkout -> svc-payments` over two provenance-bearing `DEPENDS_ON` edges.

## Configuration assumptions

- Project root is `/Users/mohammadrezakarami/Documents/New project/incidentgraph`.
- The standalone local repository is initialized on branch `main`.
- Private remote `origin` is `https://github.com/mohammadrezakarami/incidentgraph.git`.
- Default backend runtime: Python 3.12 managed for the project with uv.
- Frontend runtime: Node 24.13.1 and npm 11.8.0.
- Default hosted-model candidate: versioned OpenAI GPT-5.4 Mini snapshot, disabled until explicit provider and budget approval.
- Default local embedding candidate: `sentence-transformers/all-MiniLM-L6-v2`, with the exact Hub revision pinned during Phase 3.
- Active embedding revision: `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, 384 dimensions, CPU, batch size 16.
- Active corpus: `incidentgraph-lab-corpus-v1-466b7569b585`.
- Held-out seal: `a77524916562fdd4337e88d0efa295813fe05e0910d1a2bc1c51f9ff2d778c3c`.
- Retrieval limits: vector 20, full-text 20, RRF k=60, graph depth 2, graph nodes 50, final chunks 8, final tokens 5,000.
- One worker and one active LLM investigation.
- Normal core container target: approximately 6.25 GiB aggregate; optional observability profiles off.
- No production data, external tracing, public endpoints, remediation, or paid calls.

## Open issues and honest limitations

1. The investigator, grounded incident reports, review flow, and console are not implemented yet.
2. Unit-only global coverage is 41.02 percent; the retained 85 percent later-core gate fails today.
3. The PostgreSQL checkpoint namespace exists, but actual LangGraph checkpoint tables/setup await the workflow phase.
4. GitHub CLI authentication is stale, although the private remote exists and normal Git push works.
5. No provider credential was detected; provider and monetary budget are intentionally unapproved.
6. Phase 2 captures predate the curated corpus and need recapture before final as-of evaluation pairing.
7. The 37-document corpus and 20-question development set are project-authored laboratory material; development results are not held-out or production claims.
8. Direct hybrid is slightly below vector on the development split; the current result is retained rather than tuned against held-out data.

## Next three tasks after Phase 5 approval

1. Approve a provider/model and explicit monetary/call budget, or choose a no-hosted-model Phase 5 scope.
2. Implement the single adaptive LangGraph investigator with bounded tools and stop conditions.
3. Produce claim-to-evidence grounded reports with uncertainty and contradiction handling.

## Relevant documents

- `docs/progress/phase-00-report.md`
- `docs/progress/phase-01-report.md`
- `docs/progress/phase-02-report.md`
- `docs/progress/phase-03-report.md`
- `docs/progress/phase-04-report.md`
- `docs/adr/0001-single-investigator.md`
- `docs/adr/0002-neo4j-graph-and-vectors.md`
- `docs/adr/0003-postgresql-durable-execution.md`
- `docs/adr/0004-replay-isolation.md`
- `docs/adr/0005-read-only-operational-scope.md`

## Resume procedure

Read this file, `docs/PROJECT_STATUS.md`, `docs/TASKS.md`, all phase reports, and all accepted ADRs. Compare the actual directory and Git state with this handoff. Do not repeat Phase 0/1/2/3/4. If the user says only "continue," ask for Phase 5 approval and the provider/model/cost decision because the specification requires a gate and Phase 5 introduces model use. Do not make paid calls without explicit approval.
