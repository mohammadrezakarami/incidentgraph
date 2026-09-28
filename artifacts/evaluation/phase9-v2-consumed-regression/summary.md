# Phase 9 v2 consumed-data regression

Status: **PENDING FRESH POST-CORPUS HOLDOUT**.

These numbers verify the repair on the consumed v1 cases; they are not an independent held-out result.

| Workflow | Top 1 | Top 3 | Abstention | False incidents | Task completion |
|---|---:|---:|---:|---:|---:|
| fixed | 3/20 | 3/20 | 0/5 | 4/5 | 19/30 |
| adaptive | 3/20 | 3/20 | 0/5 | 2/5 | 16/30 |

## Regression checks

- `diagnosis_top1`: **FAIL**
- `diagnosis_top3`: **FAIL**
- `appropriate_abstention`: **FAIL**
- `false_incidents`: **FAIL**
- `citation_validity`: **PASS**
- `policy_violations`: **PASS**
- `warm_p95_active_seconds`: **PASS**
- `supported_claim_rate`: **PENDING**
- `coverage`: **FAIL**

## Limitations

- The Phase 9 v1 held-out answers were opened and used for error analysis; these are development regression results, not a new held-out claim.
- A fresh post-corpus capture suite must be sealed before the final comparative gate.
- Supported factual claim rate still requires a written human rubric over at least 20 fresh reports.
- Whole-project non-integration coverage is currently 47.40%, below the unchanged 85% target; v2 does not hide or redefine that failure.
- The v1 retrieval result remains immutable and is not rerun in this regression iteration.
