# Phase 9 v3 fresh post-corpus evaluation

Status: **PENDING MANUAL REVIEW**.

| Workflow | Top 1 | Top 3 | Abstention | False incidents | Task completion |
|---|---:|---:|---:|---:|---:|
| fixed | 0/20 | 0/20 | 5/5 | 0/5 | 30/30 |
| adaptive | 0/20 | 0/20 | 3/5 | 0/5 | 30/30 |

## Automated target status

- `diagnosis_top1`: **FAIL**
- `diagnosis_top3`: **FAIL**
- `appropriate_abstention`: **FAIL**
- `false_incidents`: **PASS**
- `citation_validity`: **FAIL**
- `policy_violations`: **PASS**
- `warm_p95_active_seconds`: **PASS**
- `supported_claim_rate`: **PENDING**
- `coverage`: **FAIL**

## Limitations

- This is a small project-authored laboratory dataset, not production evidence.
- Variants sharing one capture are grouped and are not independent observations.
- Five healthy and five insufficient held-out cases provide weak statistical evidence.
- Supported factual claim rate requires the written review of at least 20 reports.
- Whole-project non-integration coverage remains below the retained 85% target.
