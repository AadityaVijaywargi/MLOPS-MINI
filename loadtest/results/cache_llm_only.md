# Load test: cache_llm_only (cache mode hit, 120s per step)

SLO: p95 submit->result <= 45 s

| users | runs | run/s | p50 s | p95 s | max s | failures | submit p95 ms | SLO met |
|---|---|---|---|---|---|---|---|---|
| 4 | 172 | 1.44 | 1.0 | 1.1 | 19.2 | 0 | 27 | yes |
