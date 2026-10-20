# Load test: friend3 (cache mode miss, 120s per step)

SLO: p95 submit->result <= 45 s

| users | runs | run/s | p50 s | p95 s | max s | failures | submit p95 ms | SLO met |
|---|---|---|---|---|---|---|---|---|
| 2 | 8 | 0.07 | 24.0 | 25.0 | 25.2 | 0 | 37 | yes |
| 4 | 17 | 0.14 | 23.0 | 25.0 | 25.2 | 0 | 42 | yes |
| 8 | 19 | 0.16 | 39.0 | 53.0 | 52.6 | 0 | 60 | NO |
| 16 | 16 | 0.13 | 89.0 | 98.0 | 98.2 | 0 | 81 | NO |
