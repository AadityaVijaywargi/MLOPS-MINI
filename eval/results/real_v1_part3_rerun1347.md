# Evaluation: real_v1_part3_rerun1347

- run at: 2026-10-21T08:27:26.903385+00:00
- variant: v1
- api: http://api:8000

| metric | value |
|---|---|
| scenarios | 6 |
| errors | 0 |
| provider_degraded | 0 |
| scored | 6 |
| route_accuracy | 1.0 |
| groundedness | 0.9762 |
| context_relevance | 1.0 |
| faithfulness | 1.0 |
| hallucination_rate | 0.0238 |
| violation_recall | 1.0 |
| mean_latency_s | 101.0167 |
| mean_cost_usd | 0.0 |
| mean_llm_calls | 20.1667 |

| id | expected | got | ctx rel | grounded | faithful | halluc | viol recall | s |
|---|---|---|---|---|---|---|---|---|
| S16 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 84.4 |
| S17 | clear-for-submission | clear-for-submission | 1.0 | 0.8571428571428571 | 1.0 | 0.14285714285714285 | None | 172.9 |
| S18 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 68.3 |
| S19 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 110.5 |
| S20 | clear-for-submission | clear-for-submission | 1.0 | 1.0 | 1.0 | 0.0 | None | 66.3 |
| S21 | clear-for-submission | clear-for-submission | 1.0 | 1.0 | 1.0 | 0.0 | None | 103.7 |
