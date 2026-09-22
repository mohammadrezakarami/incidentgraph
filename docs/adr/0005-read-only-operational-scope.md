# ADR-0005: Read-Only Operational Scope

Status: Proposed for Phase 1 approval

Date: 2026-09-22

## Context

The portfolio must demonstrate evidence-seeking investigation without creating unsafe operational authority. Accepting a diagnosis is not permission to change infrastructure.

## Decision

All agent-facing tools are read-only and selected from reviewed server-side templates. The model cannot issue shell commands, Docker operations, arbitrary Cypher/PromQL, filesystem paths, URLs, or fault-control requests. Fault injection belongs to a separate local operator control plane. Recommended next steps always have `execution_status: not_executed`.

Human review decisions accept, reject, or request revision of a report only. Any future remediation execution requires a separate ADR, permission model, explicit action authorization, preconditions, expiry, idempotency, verification, and rollback design.

## Consequences

- Prompt injection cannot grant new tool authority.
- The product is an investigation assistant, not an autonomous remediation platform.
- Security tests can assert zero unauthorized executions for a finite enumerated suite without claiming universal safety.
