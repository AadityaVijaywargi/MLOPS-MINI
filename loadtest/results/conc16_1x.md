# Load test: conc16_1x (cache mode miss, 120s per step)

SLO: p95 submit->result <= 45 s

| users | runs | run/s | p50 s | p95 s | max s | failures | submit p95 ms | SLO met |
|---|---|---|---|---|---|---|---|---|
| 16 | 86 | 0.72 | 19.0 | 21.0 | 21.5 | 0 | 180 | yes |
| 32 | 96 | 0.81 | 31.0 | 38.0 | 41.1 | 0 | 340 | yes |
