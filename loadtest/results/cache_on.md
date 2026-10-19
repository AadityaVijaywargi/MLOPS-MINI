# Load test: cache_on (cache mode hit, 120s per step)

SLO: p95 submit->result <= 45 s

| users | runs | run/s | p50 s | p95 s | max s | failures | submit p95 ms | SLO met |
|---|---|---|---|---|---|---|---|---|
| 4 | 477 | 4.00 | 0.0 | 0.0 | 0.1 | 0 | 27 | yes |
