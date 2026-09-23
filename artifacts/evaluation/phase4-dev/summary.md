# Phase 4 development retrieval evaluation

Held-out was seal-verified and was not evaluated.

| Variant | Recall@5 | MRR@5 | nDCG@5 | Mean ms |
|---|---:|---:|---:|---:|
| vector | 0.900 | 0.950 | 0.923 | 13.3 |
| hybrid | 0.883 | 0.950 | 0.921 | 12.3 |
| graph | 0.908 | 1.000 | 0.957 | 15.7 |

## Required graph-only case

`rq-dev-004`: `{"graph": true, "hybrid": false, "vector": false}`

The machine-readable `results.json` records exact node and relationship paths.
