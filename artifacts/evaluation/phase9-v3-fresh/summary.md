# Phase 9 v3 fresh post-corpus evaluation

Status: **FAIL — EVALUATION COMPLETE**.

The 120-job free-Colab evaluation reproduced byte-for-byte from the returned per-job records. The written review covers 20 actual adaptive reports and is AI-assisted, not independent human validation.

## Fresh held-out comparison

| Workflow | Top 1 | Top 3 | Abstention | False incidents | Task completion |
|---|---:|---:|---:|---:|---:|
| adaptive | 0/20 | 0/20 | 3/5 | 0/5 | 30/30 |
| fixed | 0/20 | 0/20 | 5/5 | 0/5 | 30/30 |

## Claim-support review

- Actual reports reviewed: 20
- Supported atomic factual claims: 0/20 (0.0%)
- Frozen target: at least 95%
- Result: **FAIL**

## Target status

- `appropriate_abstention`: **FAIL**
- `citation_validity`: **FAIL**
- `coverage`: **FAIL**
- `diagnosis_top1`: **FAIL**
- `diagnosis_top3`: **FAIL**
- `false_incidents`: **PASS**
- `policy_violations`: **PASS**
- `supported_claim_rate`: **FAIL**
- `warm_p95_active_seconds`: **PASS**

## Limitations

- This is a small project-authored laboratory dataset, not production evidence.
- Variants sharing one capture are grouped and are not independent observations.
- Five healthy and five insufficient held-out cases provide weak statistical evidence.
- Whole-project non-integration coverage remains below the retained 85% target.
- The written semantic rubric is AI-assisted and is not independent human validation.
- The 20 reviewed adaptive reports contained no cited factual diagnosis; each emitted only one unsupported generic conclusion.
