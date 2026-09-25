# Phase 9 frozen evaluation

Status: **FAIL — evaluation completed**.

All automated aggregates reproduce byte-for-byte from the 120 per-case records. The written claim-support review covers 20 actual reports; it is AI-assisted and is not presented as independent human validation.

## Held-out agent comparison

| Workflow | Top 1 | Top 3 | Abstention | False incidents | Task completion |
|---|---:|---:|---:|---:|---:|
| adaptive | 0/20 | 0/20 | 5/5 | 0/5 | 28/30 |
| fixed | 0/20 | 0/20 | 0/5 | 0/5 | 0/30 |

## Claim-support review

- Actual reports reviewed: 20
- Supported atomic factual claims: 32/57 (56.1%)
- Frozen target: at least 95%
- Result: **FAIL**

## Target status

- `appropriate_abstention`: **PASS**
- `citation_validity`: **FAIL**
- `coverage`: **FAIL**
- `diagnosis_top1`: **FAIL**
- `diagnosis_top3`: **FAIL**
- `false_incidents`: **PASS**
- `policy_violations`: **FAIL**
- `retrieval_recall_at_5`: **PASS**
- `supported_claim_rate`: **FAIL**
- `warm_p95_active_seconds`: **FAIL**

## Limitations

- Incident captures predate most corpus validity windows, so runbook retrieval is correctly unavailable for those cases.
- Five healthy and five insufficient held-out cases provide weak statistical evidence.
- Paraphrases and repeated development runs are not treated as independent samples.
- The retained core coverage target was not met before this run.
- The written semantic rubric is AI-assisted and is not independent human validation.
