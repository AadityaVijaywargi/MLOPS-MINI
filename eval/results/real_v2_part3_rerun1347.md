# Evaluation: real_v2_part3_rerun1347

- run at: 2026-10-21T08:37:08.281284+00:00
- variant: v2
- api: http://api:8000

| metric | value |
|---|---|
| scenarios | 6 |
| errors | 0 |
| provider_degraded | 0 |
| scored | 6 |
| route_accuracy | 0.8333 |
| groundedness | 1.0 |
| context_relevance | 1.0 |
| faithfulness | 0.9206 |
| hallucination_rate | 0.0 |
| violation_recall | 1.0 |
| mean_latency_s | 96.0667 |
| mean_cost_usd | 0.0 |
| mean_llm_calls | 21.6667 |

| id | expected | got | ctx rel | grounded | faithful | halluc | viol recall | s |
|---|---|---|---|---|---|---|---|---|
| S16 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 0.6666666666666666 | 0.0 | 1.0 | 132.6 |
| S17 | clear-for-submission | specialist-review X | 1.0 | 1.0 | 1.0 | 0.0 | None | 120.4 |
| S18 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 126.5 |
| S19 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 66.3 |
| S20 | clear-for-submission | clear-for-submission | 1.0 | 1.0 | 1.0 | 0.0 | None | 44.2 |
| S21 | clear-for-submission | clear-for-submission | 1.0 | 1.0 | 0.8571428571428571 | 0.0 | None | 86.4 |
