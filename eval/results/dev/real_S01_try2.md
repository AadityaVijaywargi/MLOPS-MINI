# Evaluation: real_S01_try2

- run at: 2026-10-19T17:38:08.936939+00:00
- variant: default
- api: http://api:8000

| metric | value |
|---|---|
| scenarios | 1 |
| errors | 0 |
| route_accuracy | 0.0 |
| groundedness | None |
| context_relevance | 1.0 |
| faithfulness | None |
| hallucination_rate | None |
| violation_recall | 0.0 |
| mean_latency_s | 14.3 |
| mean_cost_usd | 0.0 |
| mean_llm_calls | 4 |

| id | expected | got | ctx rel | grounded | faithful | halluc | viol recall | s |
|---|---|---|---|---|---|---|---|---|
| S01 | revise-and-recheck | specialist-review X | 1.0 | None | None | None | 0.0 | 14.3 |
