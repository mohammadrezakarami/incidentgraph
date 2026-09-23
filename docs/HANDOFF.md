# IncidentGraph Handoff

Last updated: 2026-09-23

## Current phase

Phase 0 through Phase 3 are complete and passed. Phase 4 is not approved yet.

Roadmap position: Phase 3 of 11 delivery phases is complete; including Phase 0, 4 of 12 gates are complete and 8 remain.

## Last verified command

Executable verification of the Phase 3 graph and corpus:

```text
make verify-ingestion
```

Result: dependency direction, reverse impact, temporal eligibility, trust filtering, index readiness, source resolution, and embedding compatibility all passed. The active corpus has 37 documents and 37 chunks; 34 are currently eligible.

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
- One worker and one active LLM investigation.
- Normal core container target: approximately 6.25 GiB aggregate; optional observability profiles off.
- No production data, external tracing, public endpoints, remediation, or paid calls.

## Open issues and honest limitations

1. The investigator, retrieval comparison, reports, review flow, and console are not implemented yet.
2. Unit-only global coverage is 38.71 percent; the retained 85 percent later-core gate fails today.
3. The PostgreSQL checkpoint namespace exists, but actual LangGraph checkpoint tables/setup await the workflow phase.
4. GitHub CLI authentication is stale, although the private remote exists and normal Git push works.
5. No provider credential was detected; provider and monetary budget are intentionally unapproved.
6. Phase 2 captures predate the curated corpus and need recapture before final as-of evaluation pairing.
7. The 37-document corpus is project-authored laboratory material and has not yet been evaluated for retrieval quality.

## Next three tasks after Phase 4 approval

1. Implement vector, hybrid, and graph-enhanced retrievers behind one bounded interface.
2. Add annotated development retrieval questions and executable ranking metrics.
3. Compare all three variants on the same corpus snapshot, cutoff, and context budget.

## Relevant documents

- `docs/progress/phase-00-report.md`
- `docs/progress/phase-01-report.md`
- `docs/progress/phase-02-report.md`
- `docs/progress/phase-03-report.md`
- `docs/adr/0001-single-investigator.md`
- `docs/adr/0002-neo4j-graph-and-vectors.md`
- `docs/adr/0003-postgresql-durable-execution.md`
- `docs/adr/0004-replay-isolation.md`
- `docs/adr/0005-read-only-operational-scope.md`

## Resume procedure

Read this file, `docs/PROJECT_STATUS.md`, `docs/TASKS.md`, all phase reports, and all accepted ADRs. Compare the actual directory and Git state with this handoff. Do not repeat Phase 0/1/2/3. If the user says only "continue," ask for Phase 4 approval because the specification requires a gate between phases. Do not begin retrieval implementation until that approval exists.
