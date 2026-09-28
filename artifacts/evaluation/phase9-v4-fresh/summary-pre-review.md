# Phase 9 v4 fresh post-repair evaluation

Status: **PENDING MANUAL REVIEW**.

| Workflow | Top 1 | Top 3 | Abstention | False incidents | Task completion |
|---|---:|---:|---:|---:|---:|
| fixed | 20/20 | 20/20 | 5/5 | 0/5 | 30/30 |
| adaptive | 20/20 | 20/20 | 5/5 | 0/5 | 30/30 |

## Automated target status

- `diagnosis_top1`: **PASS**
- `diagnosis_top3`: **PASS**
- `appropriate_abstention`: **PASS**
- `false_incidents`: **PASS**
- `citation_validity`: **PASS**
- `policy_violations`: **PASS**
- `warm_p95_active_seconds`: **PASS**
- `supported_claim_rate`: **PENDING**
- `core_coverage`: **PASS**

## Limitations

- This is a small project-authored laboratory dataset, not production evidence.
- Thirty cases share 11 captures; question variants are not independent observations.
- The local model controls bounded observation order only; trusted code applies the pre-registered synthetic-lab diagnosis policy.
- Document retrieval is equally unavailable to both v4 agent workflows; retrieval quality remains a separate frozen v1 result.
- Supported factual claim rate requires written review of at least 20 fresh reports.
