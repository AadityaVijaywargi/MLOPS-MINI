# Load test: scaled_3x (cache mode miss, 120s per step)

SLO: p95 submit->result <= 45 s

| users | runs | run/s | p50 s | p95 s | max s | failures | submit p95 ms | SLO met |
|---|---|---|---|---|---|---|---|---|
| 2 | 11 | 0.09 | 19.0 | 23.0 | 23.2 | 0 | 61 | yes |
| 4 | 22 | 0.18 | 19.0 | 22.0 | 22.2 | 0 | 50 | yes |
| 8 | 45 | 0.38 | 19.0 | 21.0 | 22.2 | 0 | 88 | yes |
| 16 | 78 | 0.65 | 21.0 | 30.0 | 31.7 | 0 | 140 | yes |
| 32 | 65 | 0.54 | 43.0 | 53.0 | 53.1 | 0 | 240 | NO |
