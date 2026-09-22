# ADR-0003: PostgreSQL-Backed Durable Execution

Status: Proposed for Phase 1 approval

Date: 2026-09-22

## Context

Investigations must survive worker interruption, support human review, stream ordered events, and avoid duplicate publication. LangGraph checkpoints record workflow state but do not provide job scheduling, leases, or stale-worker fencing.

## Decision

Use one application PostgreSQL service for investigation records, a small job queue, leases, heartbeats, attempt fencing, events, evidence metadata, reports, reviews, and a logically separate supported LangGraph PostgreSQL checkpoint schema. Use short claim transactions and never hold a transaction across an LLM/tool call. Use at-least-once execution with idempotent side effects; do not claim exactly-once delivery.

Use a separate PostgreSQL container for the lab checkout workload so fault injection cannot starve or corrupt durable investigation state.

## Consequences

- Queue delivery and graph resume are independently testable.
- One durable technology avoids an unnecessary broker.
- Stale workers require fencing tokens on every publication path.
- Recovery tests must cover interruption around tool calls, checkpoints, publication, and review waits.
