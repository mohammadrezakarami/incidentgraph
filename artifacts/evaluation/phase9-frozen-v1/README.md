# Phase 9 frozen evaluation artifacts

Status: **awaiting free-Colab execution**.

The frozen configuration is `config/phase9-freeze-v1.json`. Raw shard files and the held-out
retrieval artifact are intentionally not committed before execution. After all 120 agent jobs,
`incidentgraph-phase9-eval finalize` produces:

- `aggregate.json`
- `per-case.csv`
- `summary.md`
- `manual-review.jsonl`

The manual-review file must contain completed rubrics for at least 20 sampled reports before the
supported-claim metric or Phase 9 gate can be decided. No paid API is permitted.
