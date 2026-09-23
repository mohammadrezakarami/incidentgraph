# ADR-0004: Immutable Replay Isolation

Status: Accepted

Date: 2026-09-22

## Context

Fair comparisons require every variant to see the same observations available at the same cutoff. Live topology, later documents, or evaluator-only fault labels would invalidate the benchmark.

## Decision

Expose LIVE and REPLAY through the same typed observation interfaces. A replay snapshot is immutable, content-addressed, has an observation cutoff, and references explicit topology/corpus versions. Runtime adapters reject evidence after the cutoff. Evaluator-only labels, injector parameters, and accepted answers remain outside API/worker image contexts and mounts. Snapshot IDs are opaque.

## Consequences

- Tool behavior can be compared without changing agent contracts.
- Snapshot creation must capture provenance and hashes for metrics, logs, topology, changes, and corpus eligibility.
- Replay cannot silently fall back to a live source.
- Documents created after a capture are ineligible unless the scenario is recaptured.
