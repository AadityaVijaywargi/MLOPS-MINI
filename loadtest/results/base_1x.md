# Load test: base_1x (cache mode miss, 120s per step)

SLO: p95 submit->result <= 45 s

| users | runs | run/s | p50 s | p95 s | max s | failures | submit p95 ms | SLO met |
|---|---|---|---|---|---|---|---|---|
| 2 | 11 | 0.09 | 19.0 | 20.0 | 20.2 | 0 | 45 | yes |
| 4 | 20 | 0.17 | 19.0 | 22.0 | 22.2 | 0 | 53 | yes |
| 8 | 24 | 0.20 | 31.0 | 35.0 | 37.4 | 0 | 70 | yes |
| 16 | 16 | 0.13 | 66.0 | 75.0 | 74.9 | 0 | 110 | NO |
| 32 | 12 | 0.10 | 113.0 | 118.0 | 117.8 | 0 | 240 | NO |
