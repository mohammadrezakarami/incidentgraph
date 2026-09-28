# Phase 9 repair-3 development policy replay

This is a lightweight replay over the already-consumed ten-case v3 development repeat subset plus
the omitted healthy-high-traffic development capture, reconstructed deterministically from its
immutable capture. It made no model, network, Docker, or paid-provider calls. The replay verifies
the trusted bounded-policy path introduced after repair-2 demonstrated that the pinned 4B model
could still over-abstain and misdescribe numeric facts.

## Result

- Structurally valid reports: **11/11**
- Deterministic support checks: **11/11**
- Label match: **11/11**
  - identifiable: **7/7**
  - insufficient/ambiguous: **2/2**
  - healthy: **2/2**
- Model calls: **0**
- Paid cost: **USD 0**

The trusted policy scopes dependency errors, changes, pool, cache, CPU, and latency to their exact
services and edges. It creates a derived evidence record cryptographically linked to the complete
source trace and all raw evidence IDs, then renders only the exact supporting facts. The model no
longer supplies scored diagnosis prose or changes the bounded decision.

## What this does not prove

This is development replay, not a fresh holdout and not an end-to-end adaptive workflow run. The
85% global coverage target and independent human supported-claim review remain open. Therefore
this result does **not** authorize a Phase 9 PASS or a fresh full run by itself.

`manifest.json` pins the source subset, repair code, v3 cases, evaluator labels, and source freeze
by SHA-256. `records.json` preserves the per-case policy packet, exact selected fact references,
derived evidence, report, and source-trace digest.
