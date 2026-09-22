# IncidentGraph Handoff

Last updated: 2026-09-22

## Current phase

Phase 0, Phase 1, and Phase 2 are complete and passed. Phase 3 is not approved yet.

## Last verified command

Executable verification of all eligible Phase 2 captures:

```text
make verify-captures
```

Result: 17 captures total; 12 independent fault captures and 5 controls; hashes, telemetry signals, trace continuity, evaluator separation, and recovery all passed.

## Configuration assumptions

- Project root is `/Users/mohammadrezakarami/Documents/New project/incidentgraph`.
- The standalone local repository is initialized on branch `main`.
- Private remote `origin` is `https://github.com/mohammadrezakarami/incidentgraph.git`.
- Default backend runtime: Python 3.12 managed for the project with uv.
- Frontend runtime: Node 24.13.1 and npm 11.8.0.
- Default hosted-model candidate: versioned OpenAI GPT-5.4 Mini snapshot, disabled until explicit provider and budget approval.
- Default local embedding candidate: `sentence-transformers/all-MiniLM-L6-v2`, with the exact Hub revision pinned during Phase 3.
- One worker and one active LLM investigation.
- Normal core container target: approximately 6.25 GiB aggregate; optional observability profiles off.
- No production data, external tracing, public endpoints, remediation, or paid calls.

## Open issues and honest limitations

1. The investigator, knowledge ingestion, retrieval, reports, review flow, and console are not implemented yet.
2. Unit-only global coverage is 32.69 percent; the retained 85 percent later-core gate fails today.
3. The PostgreSQL checkpoint namespace exists, but actual LangGraph checkpoint tables/setup await the workflow phase.
4. GitHub CLI authentication is stale, although the private remote exists and normal Git push works.
5. No provider credential was detected; provider and monetary budget are intentionally unapproved.
6. Phase 2 captures predate the curated corpus and need recapture before final as-of evaluation pairing.

## Next three tasks after Phase 3 approval

1. Define Neo4j constraints and the authoritative, versioned lab topology.
2. Create and validate the curated corpus manifest before embedding.
3. Benchmark the pinned local embedding model on CPU, then build idempotent full-text/vector ingestion.

## Relevant documents

- `docs/progress/phase-00-report.md`
- `docs/progress/phase-01-report.md`
- `docs/progress/phase-02-report.md`
- `docs/adr/0001-single-investigator.md`
- `docs/adr/0002-neo4j-graph-and-vectors.md`
- `docs/adr/0003-postgresql-durable-execution.md`
- `docs/adr/0004-replay-isolation.md`
- `docs/adr/0005-read-only-operational-scope.md`

## Resume procedure

Read this file, `docs/PROJECT_STATUS.md`, `docs/TASKS.md`, all phase reports, and all accepted ADRs. Compare the actual directory and Git state with this handoff. Do not repeat Phase 0/1/2. If the user says only "continue," ask for Phase 3 approval because the specification requires a gate between phases. Do not begin graph/corpus ingestion until that approval exists.
