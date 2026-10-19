# Load test: compaction_check (cache mode miss, 120s per step)

SLO: p95 submit->result <= 45 s

| users | runs | run/s | p50 s | p95 s | max s | failures | submit p95 ms | SLO met |
|---|---|---|---|---|---|---|---|---|
| 4 | 22 | 0.18 | 19.0 | 20.0 | 20.2 | 0 | 44 | yes |
