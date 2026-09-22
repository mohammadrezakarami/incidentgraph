# IncidentGraph

IncidentGraph is a production-inspired, evidence-grounded agent for investigating controlled infrastructure incidents. It is designed to combine an adaptive LangGraph workflow, LangChain model and tool contracts, Neo4j-backed graph-enhanced retrieval, durable PostgreSQL execution, and real laboratory telemetry.

## Current status

Phase 0 (discovery, architecture, and feasibility) is complete. Phase 1 (reproducible foundation and contracts) is in progress. No investigator, benchmark result, or production capability is claimed yet.

See:

- [`docs/progress/phase-00-report.md`](docs/progress/phase-00-report.md)
- [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md)
- [`docs/TASKS.md`](docs/TASKS.md)
- [`docs/HANDOFF.md`](docs/HANDOFF.md)

## Safety boundary

The planned agent is read-only. It will not execute remediation, control Docker, inject faults, generate arbitrary shell/Cypher/PromQL, or access production systems.
