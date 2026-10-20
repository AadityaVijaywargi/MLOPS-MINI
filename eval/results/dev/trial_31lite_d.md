# Evaluation: trial_31lite_d

- run at: 2026-10-19T20:17:02.373135+00:00
- variant: v1
- api: http://api:8000

| metric | value |
|---|---|
| scenarios | 3 |
| errors | 0 |
| route_accuracy | 0.3333 |
| groundedness | 0.9167 |
| context_relevance | 1.0 |
| faithfulness | 0.9524 |
| hallucination_rate | 0.0833 |
| violation_recall | 0.5 |
| mean_latency_s | 168.3 |
| mean_cost_usd | 0.0 |
| mean_llm_calls | 30.6667 |

| id | expected | got | ctx rel | grounded | faithful | halluc | viol recall | s |
|---|---|---|---|---|---|---|---|---|
| S01 | revise-and-recheck | revise-and-recheck | 1.0 | 0.75 | 1.0 | 0.25 | 0.5 | 198.8 |
| S02 | clear-for-submission | specialist-review X | 1.0 | 1.0 | 0.8571428571428571 | 0.0 | None | 160.5 |
| S06 | clear-for-submission | specialist-review X | 1.0 | 1.0 | 1.0 | 0.0 | None | 145.6 |
