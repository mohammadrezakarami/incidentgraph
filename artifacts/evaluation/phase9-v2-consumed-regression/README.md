# Phase 9 v2 consumed-data regression

This directory preserves the completed zero-paid-cost Colab run returned on 2026-09-28. All 120
planned jobs completed. Re-running `finalize` from the twelve `agent-part` files reproduced
`aggregate.json`, `per-case.csv`, and `summary.md` byte-for-byte.

This is a development regression over the opened Phase 9 v1 cases. It is not a fresh held-out
result and cannot replace the final post-corpus gate.

## Integrity

- Returned ZIP SHA-256: `7ef158e2a1db24c0bc052513a267348b514eaa1779e2757eb8870c6c38a88e66`
- Aggregate SHA-256: `bbc53a3533b755326ad37ba6b723d3c9f56fc4339c90e1fa9ee34e7694e5793d`
- Per-case SHA-256: `dad4eb26dc62c67260a4a5278a3ef4e9fc82189b16a4b0e5535aa00d991b7ac3`
- Summary SHA-256: `b4a2c4df1c1edf1bd55752734d55fc660cb35a3d88ab5666b91c8a69d748b5cc`

## Measured result

| Workflow | Top 1 | Top 3 | Abstention | False incidents | Task completion |
|---|---:|---:|---:|---:|---:|
| fixed | 3/20 | 3/20 | 0/5 | 4/5 | 19/30 |
| adaptive | 3/20 | 3/20 | 0/5 | 2/5 | 16/30 |

Citation validity, blocked-policy-attempt count, and warm p95 latency passed. Diagnosis, abstention,
false-incident, and coverage targets failed; factual-claim support remains pending.

## Error analysis

Across all 120 jobs, 57 reports were lost to strict schema coherence validators and two to model
timeouts. The schema failures were 49 outcome/mechanism mismatches, six finish/bundle mismatches,
and two non-causal component mismatches. These are adapter failures rather than unauthorized tool
executions.

Among valid held-out reports, the model over-selected `cache_degradation`: 13 of 19 fixed probable
causes and 11 of 16 adaptive probable causes. The compact evidence exposed raw cache miss-rate
series without a baseline, ratio, or explicit abnormality threshold, so ordinary nonzero misses were
frequently treated as causal. The next version must normalize harmless structured-output variants
without accepting unsafe requests and must expose deterministic, unit-aware derived signals before
any fresh holdout is sealed.
