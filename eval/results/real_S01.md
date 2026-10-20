# Evaluation: real_S01

- run at: 2026-10-19T18:27:44.896955+00:00
- variant: default
- api: http://api:8000

| metric | value |
|---|---|
| scenarios | 1 |
| errors | 0 |
| route_accuracy | 1.0 |
| groundedness | None |
| context_relevance | 1.0 |
| faithfulness | None |
| hallucination_rate | None |
| violation_recall | 1.0 |
| mean_latency_s | 79.5 |
| mean_cost_usd | 0.0 |
| mean_llm_calls | 21 |

| id | expected | got | ctx rel | grounded | faithful | halluc | viol recall | s |
|---|---|---|---|---|---|---|---|---|
| S01 | revise-and-recheck | revise-and-recheck | 1.0 | None | None | None | 1.0 | 79.5 |
