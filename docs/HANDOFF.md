# IncidentGraph Handoff

Last updated: 2026-09-22

## Current phase

Phase 0 is complete and passed. Phase 1 is approved and in progress.

## Last verified command

Read-only Docker engine inspection:

```text
docker version --format 'client={{.Client.Version}} server={{.Server.Version}} os={{.Server.Os}} arch={{.Server.Arch}}'
```

Result: Docker client/server 29.4.1 is running on Linux/ARM64 with 10 CPUs and approximately 8 GiB assigned. No project container or service verification has passed yet.

## Configuration assumptions

- Project root will be `/Users/mohammadrezakarami/Documents/New project/incidentgraph`.
- The standalone local repository is initialized on branch `main`.
- Private remote `origin` is `https://github.com/mohammadrezakarami/incidentgraph.git`.
- Default backend runtime: Python 3.12 managed for the project with uv.
- Frontend runtime: Node 24.13.1 and npm 11.8.0.
- Default hosted-model candidate: versioned OpenAI GPT-5.4 Mini snapshot, disabled until explicit provider and budget approval.
- Default local embedding candidate: `sentence-transformers/all-MiniLM-L6-v2`, with the exact Hub revision pinned during Phase 3.
- One worker and one active LLM investigation.
- Normal core container target: approximately 6.25 GiB aggregate; optional observability profiles off.
- No production data, external tracing, public endpoints, remediation, or paid calls.

## Unresolved issues

1. Python 3.12 and uv are not installed for this project.
2. Exact Python and image pins/digests require joint resolution and runtime probes.
3. GitHub CLI authentication is stale, although the private repository was created through the existing authenticated browser session.
4. No provider credential was detected; account/model availability is unknown.
5. Provider and monetary budget are intentionally unapproved.

## Next three tasks after approval

1. Bootstrap pinned uv/Python 3.12 and run a minimal dependency-resolution/import probe.
2. Pin/probe PostgreSQL and Neo4j containers.
3. Implement typed configuration and the non-AI durable queue slice.

## Relevant documents

- `docs/progress/phase-00-report.md`
- `docs/adr/0001-single-investigator.md`
- `docs/adr/0002-neo4j-graph-and-vectors.md`
- `docs/adr/0003-postgresql-durable-execution.md`
- `docs/adr/0004-replay-isolation.md`
- `docs/adr/0005-read-only-operational-scope.md`

## Resume procedure

Read this file, `docs/PROJECT_STATUS.md`, `docs/TASKS.md`, the Phase 0 report, and all accepted ADRs. Compare the actual directory and Git state with this handoff. Do not restart Phase 0 or generate a second architecture. If the user says only "continue," confirm Phase 1 approval from conversation context, inspect Docker daemon status, and resume the first unfinished Phase 1 task.
