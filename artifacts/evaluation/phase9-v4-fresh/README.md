# Phase 9 v4 fresh post-repair evaluation

This directory preserves the final separately frozen Phase 9 repair evaluation. The free-Colab
run used the pinned `qwen3:4b-instruct-2507-q4_K_M` model only to order bounded observation bundles
and completed all 120 planned jobs at an estimated monetary cost of USD 0. Trusted frozen code
applied the pre-registered synthetic-lab diagnosis and citation policy.

## Provenance and reproduction

- Returned archive SHA-256:
  `47f77a40175203d3f2ee4d44e2b7baf5d26e4d9de1a7046ab238e5913fd98bcc`
- Reproduced pre-review aggregate SHA-256:
  `e8aa980e89696a9529324289508cb07bfbdc7abba5ae1f9f625d3271ddbebe57`
- Reproduced per-case CSV SHA-256:
  `7f7f0259d72d8c19aa13ec2e33f068ab1e78e45f95932f5f12f3207ec1108c46`
- Final post-review aggregate SHA-256:
  `7b29a6f1ff32704a6effe80842225f8a9dee7cb82e97e2b652ce3f09e2f9c36b`

`aggregate-pre-review.json` and `summary-pre-review.md` are the byte-for-byte Colab outputs.
Running the frozen finalizer over the twelve `agent-part-*.jsonl` files reproduced both the
pre-review aggregate and `per-case.csv` exactly. The written rubric can be reproduced while the
original returned archive is available with:

```bash
.venv/bin/python scripts/complete_phase9_v4_manual_review.py \
  artifacts/evaluation/phase9-v4-fresh \
  --source-archive /path/to/phase9-v4-progress.zip
```

## Result

Both workflows reached Top 1 20/20, Top 3 20/20, appropriate abstention 5/5, zero false incidents,
30/30 task completion, and 100% citation validity. The adaptive path recorded zero policy
violations and a warm p95 of 1.819 seconds. Retained branch-aware core coverage is 85.14%.

The manual semantic review covers all 20 identifiable adaptive held-out reports in case order. It
found 69/69 supported atomic factual claims, so the final v4 quality gate is **PASS**. The review is
AI-assisted and is not independent human validation. The 20 reviewed report variants represent
seven independent capture groups; the complete 30-case fixture shares 11 captures. This is a
small project-authored laboratory result, not production evidence.
