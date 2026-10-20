# Evaluation: real_v2_part1_rerun0054

- run at: 2026-10-20T20:03:42.102288+00:00
- variant: v2
- api: http://api:8000

| metric | value |
|---|---|
| scenarios | 7 |
| errors | 0 |
| provider_degraded | 2 |
| scored | 5 |
| route_accuracy | 1.0 |
| groundedness | 1.0 |
| context_relevance | 1.0 |
| faithfulness | 0.9714 |
| hallucination_rate | 0.0 |
| violation_recall | 1.0 |
| mean_latency_s | 170.74 |
| mean_cost_usd | 0.0 |
| mean_llm_calls | 17.2 |

| id | expected | got | ctx rel | grounded | faithful | halluc | viol recall | s |
|---|---|---|---|---|---|---|---|---|
| S01 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 130.5 |
| S02 | clear-for-submission | clear-for-submission | 1.0 | 1.0 | 1.0 | 0.0 | None | 138.6 |
| S03 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 64.3 |
| S04 | revise-and-recheck | specialist-review (provider down, not scored) | 1.0 | None | None | None | 0.0 | 120.5 |
| S05 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 0.8571428571428571 | 0.0 | 1.0 | 269.3 |
| S06 | clear-for-submission | clear-for-submission | 1.0 | 1.0 | 1.0 | 0.0 | None | 251.0 |
| S08 | clear-for-submission | specialist-review (provider down, not scored) | 1.0 | None | None | None | None | 120.5 |
