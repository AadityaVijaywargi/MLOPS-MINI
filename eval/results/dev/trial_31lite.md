# Evaluation: trial_31lite

- run at: 2026-10-19T19:47:58.789637+00:00
- variant: v1
- api: http://api:8000

| metric | value |
|---|---|
| scenarios | 2 |
| errors | 0 |
| route_accuracy | 0.5 |
| groundedness | 1.0 |
| context_relevance | 0.8333 |
| faithfulness | 1.0 |
| hallucination_rate | 0.0 |
| violation_recall | 0.5 |
| mean_latency_s | 122.85 |
| mean_cost_usd | 0.0 |
| mean_llm_calls | 17 |

| id | expected | got | ctx rel | grounded | faithful | halluc | viol recall | s |
|---|---|---|---|---|---|---|---|---|
| S01 | revise-and-recheck | revise-and-recheck | 0.6666666666666666 | 1.0 | 1.0 | 0.0 | 0.5 | 123.7 |
| S02 | clear-for-submission | specialist-review X | 1.0 | None | None | None | None | 122.0 |
