# Phase 9 v3 fresh held-out evaluation

This directory preserves the completed fresh post-corpus evaluation. The free-Colab run used the
frozen `qwen3:4b-instruct-2507-q4_K_M` model and completed all 120 planned jobs at an estimated
monetary cost of USD 0.

## Provenance and reproduction

- Returned archive SHA-256:
  `2345d2b070f26806cdfb96a874eb637e30e381c0562a5829aee08cd2ecbdde09`
- Reproduced pre-review aggregate SHA-256:
  `e9a2cb42e31f3aadbf0111796093084ddc9c3287cddbb08ea5a99541385808ce`
- Reproduced per-case CSV SHA-256:
  `8a8effb01a46962629a66b55693d325f1989424cb5a50f5aa8194583413c55c7`
- Final post-review aggregate SHA-256:
  `070c4f673efc64af9d3703a99a47b4346394d8e52f8ac4b3897021813b5b146d`

`aggregate-pre-review.json` and `summary-pre-review.md` are the byte-for-byte Colab outputs.
Running the frozen finalizer over the twelve `agent-part-*.jsonl` files reproduced both the
pre-review aggregate and `per-case.csv` exactly. The written rubric can be reproduced while the
original returned archive is available with:

```bash
.venv/bin/python scripts/complete_phase9_v3_manual_review.py \
  artifacts/evaluation/phase9-v3-fresh \
  --source-archive /path/to/phase9-v3-progress.zip
```

The manual semantic review covers the 20 held-out identifiable adaptive reports in case order. It
is AI-assisted and is not independent human validation. The final v3 quality gate is **FAIL**.
