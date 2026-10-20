# Evaluation: real_v1_part1_rerun0143

- run at: 2026-10-20T20:16:14.848677+00:00
- variant: v1
- api: http://api:8000

| metric | value |
|---|---|
| scenarios | 3 |
| errors | 0 |
| provider_degraded | 0 |
| scored | 3 |
| route_accuracy | 0.6667 |
| groundedness | 1.0 |
| context_relevance | 1.0 |
| faithfulness | 1.0 |
| hallucination_rate | 0.0 |
| violation_recall | 0.6667 |
| mean_latency_s | 55.5667 |
| mean_cost_usd | 0.0 |
| mean_llm_calls | 17 |

| id | expected | got | ctx rel | grounded | faithful | halluc | viol recall | s |
|---|---|---|---|---|---|---|---|---|
| S03 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 30.2 |
| S04 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 54.2 |
| S07 | revise-and-recheck | specialist-review X | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 82.3 |
