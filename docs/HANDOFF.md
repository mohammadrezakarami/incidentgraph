# IncidentGraph Handoff

Last updated: 2026-09-22

## Current phase

Phase 0 and Phase 1 are complete and passed. Phase 2 is not approved yet.

## Last verified command

Real PostgreSQL/Neo4j connectivity after safe teardown and restart:

```text
make smoke
```

Result: `{"postgres": true, "neo4j": true}`. All three Phase 1 containers are healthy, and the persisted investigation count remained 1 across `down`/`up`.

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

1. The investigator, lab telemetry, retrieval, reports, review flow, and console are not implemented yet.
2. Unit-only global coverage is 51.09 percent; the retained 85 percent later-core gate fails today.
3. The PostgreSQL checkpoint namespace exists, but actual LangGraph checkpoint tables/setup await the workflow phase.
4. GitHub CLI authentication is stale, although the private remote exists and normal Git push works.
5. No provider credential was detected; provider and monetary budget are intentionally unapproved.

## Next three tasks after Phase 2 approval

1. Define the smallest three-service transaction lab and telemetry contracts.
2. Add bounded workload, loopback-only fault control, and the first healthy run.
3. Implement and independently capture the six required fault families without exposing evaluator labels to the agent path.

## Relevant documents

- `docs/progress/phase-00-report.md`
- `docs/progress/phase-01-report.md`
- `docs/adr/0001-single-investigator.md`
- `docs/adr/0002-neo4j-graph-and-vectors.md`
- `docs/adr/0003-postgresql-durable-execution.md`
- `docs/adr/0004-replay-isolation.md`
- `docs/adr/0005-read-only-operational-scope.md`

## Resume procedure

Read this file, `docs/PROJECT_STATUS.md`, `docs/TASKS.md`, both phase reports, and all accepted ADRs. Compare the actual directory and Git state with this handoff. Do not repeat Phase 0/1. If the user says only "continue," ask for Phase 2 approval because the specification requires a gate between phases. Do not begin the lab until that approval exists.
