# ADR-0001: One Adaptive Investigator

Status: Proposed for Phase 1 approval

Date: 2026-09-22

## Context

IncidentGraph must adapt its next observation to evidence while preserving bounded execution, inspectable state, human review, and deterministic policy enforcement. Multiple autonomous agents would add coordination, state merging, duplicated calls, and evaluation ambiguity without being required by the core user journeys.

## Decision

Use one LLM-driven investigator inside a custom LangGraph state graph. Deterministic nodes own authentication, authorization, query bounds, budget accounting, evidence normalization, numerical calculations, citation validation, and state transitions. The model may choose only among registered read-only tools and may propose completion, clarification, or another observation.

## Consequences

- Adaptive behavior is attributable to a single controlled loop.
- Tool traces and cost comparisons remain interpretable.
- Parallel read-only tools are disabled until merge/idempotency tests pass.
- Multi-agent collaboration remains an extension after the core evaluation gates.
