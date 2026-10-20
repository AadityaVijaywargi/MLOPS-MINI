# Evaluation: trial_31lite_c

- run at: 2026-10-19T20:03:13.559751+00:00
- variant: v1
- api: http://api:8000

| metric | value |
|---|---|
| scenarios | 2 |
| errors | 0 |
| route_accuracy | 0.5 |
| groundedness | 1.0 |
| context_relevance | 1.0 |
| faithfulness | 1.0 |
| hallucination_rate | 0.0 |
| violation_recall | None |
| mean_latency_s | 116.45 |
| mean_cost_usd | 0.0 |
| mean_llm_calls | 19.5 |

| id | expected | got | ctx rel | grounded | faithful | halluc | viol recall | s |
|---|---|---|---|---|---|---|---|---|
| S02 | clear-for-submission | clear-for-submission | 1.0 | 1.0 | 1.0 | 0.0 | None | 107.6 |
| S06 | clear-for-submission | revise-and-recheck X | 1.0 | 1.0 | 1.0 | 0.0 | None | 125.3 |
