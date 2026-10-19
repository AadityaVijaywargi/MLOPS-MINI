# Load test: cache_off (cache mode hit, 120s per step)

SLO: p95 submit->result <= 45 s

| users | runs | run/s | p50 s | p95 s | max s | failures | submit p95 ms | SLO met |
|---|---|---|---|---|---|---|---|---|
| 4 | 21 | 0.18 | 19.0 | 21.0 | 22.2 | 0 | 62 | yes |
