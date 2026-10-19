# Load test: conc64_1x (cache mode miss, 150s per step)

SLO: p95 submit->result <= 45 s

| users | runs | run/s | p50 s | p95 s | max s | failures | submit p95 ms | SLO met |
|---|---|---|---|---|---|---|---|---|
| 64 | 388 | 2.60 | 22.0 | 25.0 | 28.1 | 0 | 490 | yes |
