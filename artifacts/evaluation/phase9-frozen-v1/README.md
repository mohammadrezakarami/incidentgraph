# Phase 9 frozen evaluation artifacts

Status: **evaluation complete — gate FAIL**.

The frozen configuration is `config/phase9-freeze-v1.json`. This directory contains the returned
free-Colab run, including all 120 agent jobs and the held-out retrieval artifact:

- `aggregate.json`
- `per-case.csv`
- `summary.md`
- `manual-review.jsonl`
- `manual-review-summary.json`

The original 20-row template included 10 fixed-workflow rows with no report because the fixed prompt
exceeded the model context. Those rows are retained, and adaptive held-out cases 11–20 were added
deterministically so the rubric covers 20 actual reports. The supported factual claim rate is 32/57
(56.1%), below the frozen 95% target. The review is AI-assisted and is not represented as independent
human validation. The source archive SHA-256 and aggregate-reproduction hashes are recorded in
`manual-review-summary.json`. No paid API was used.
