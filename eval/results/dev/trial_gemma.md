# Evaluation: trial_gemma

- run at: 2026-10-19T19:42:13.445778+00:00
- variant: v1
- api: http://api:8000

| metric | value |
|---|---|
| scenarios | 2 |
| errors | 0 |
| route_accuracy | 0.0 |
| groundedness | None |
| context_relevance | 0.6667 |
| faithfulness | None |
| hallucination_rate | None |
| violation_recall | 0.0 |
| mean_latency_s | 90.05 |
| mean_cost_usd | 0.0 |
| mean_llm_calls | 3.5 |

| id | expected | got | ctx rel | grounded | faithful | halluc | viol recall | s |
|---|---|---|---|---|---|---|---|---|
| S01 | revise-and-recheck | specialist-review X | 0.3333333333333333 | None | None | None | 0.0 | 177.9 |
| S02 | clear-for-submission | specialist-review X | 1.0 | None | None | None | None | 2.2 |
