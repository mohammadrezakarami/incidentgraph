# Phase 9 v4 fresh post-repair evaluation

Status: **PASS — EVALUATION COMPLETE**.

The 120-job free-Colab output reproduced byte-for-byte from its per-job records. The written review covers 20 actual adaptive reports and is AI-assisted, not independent human validation.

## Fresh held-out comparison

| Workflow | Top 1 | Top 3 | Abstention | False incidents | Task completion |
|---|---:|---:|---:|---:|---:|
| adaptive | 20/20 | 20/20 | 5/5 | 0/5 | 30/30 |
| fixed | 20/20 | 20/20 | 5/5 | 0/5 | 30/30 |

## Claim-support review

- Actual reports reviewed: 20
- Independent capture groups represented: 7
- Supported atomic factual claims: 69/69 (100.0%)
- Frozen target: at least 95%
- Result: **PASS**

## Target status

- `appropriate_abstention`: **PASS**
- `citation_validity`: **PASS**
- `core_coverage`: **PASS**
- `diagnosis_top1`: **PASS**
- `diagnosis_top3`: **PASS**
- `false_incidents`: **PASS**
- `policy_violations`: **PASS**
- `supported_claim_rate`: **PASS**
- `warm_p95_active_seconds`: **PASS**

## Limitations

- This is a small project-authored laboratory dataset, not production evidence.
- Thirty cases share 11 captures; question variants are not independent observations.
- The local model controls bounded observation order only; trusted code applies the pre-registered synthetic-lab diagnosis policy.
- Document retrieval is equally unavailable to both v4 agent workflows; retrieval quality remains a separate frozen v1 result.
- The written semantic rubric is AI-assisted and is not independent human validation.
- The 20 reviewed reports represent seven independent capture groups; variants sharing one capture are not independent evidence.
