# Evaluation: trial_31lite_b

- run at: 2026-10-19T19:56:11.939850+00:00
- variant: v1
- api: http://api:8000

| metric | value |
|---|---|
| scenarios | 2 |
| errors | 0 |
| route_accuracy | 0.0 |
| groundedness | 1.0 |
| context_relevance | 1.0 |
| faithfulness | 1.0 |
| hallucination_rate | 0.0 |
| violation_recall | None |
| mean_latency_s | 177.3 |
| mean_cost_usd | 0.0 |
| mean_llm_calls | 25 |

| id | expected | got | ctx rel | grounded | faithful | halluc | viol recall | s |
|---|---|---|---|---|---|---|---|---|
| S02 | clear-for-submission | specialist-review X | 1.0 | 1.0 | 1.0 | 0.0 | None | 123.5 |
| S06 | clear-for-submission | specialist-review X | 1.0 | 1.0 | 1.0 | 0.0 | None | 231.1 |
