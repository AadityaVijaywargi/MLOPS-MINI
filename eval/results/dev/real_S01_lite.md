# Evaluation: real_S01_lite

- run at: 2026-10-19T18:24:44.466179+00:00
- variant: default
- api: http://api:8000

| metric | value |
|---|---|
| scenarios | 1 |
| errors | 0 |
| route_accuracy | 0.0 |
| groundedness | 1.0 |
| context_relevance | 1.0 |
| faithfulness | 1.0 |
| hallucination_rate | 0.0 |
| violation_recall | 0.0 |
| mean_latency_s | 145.1 |
| mean_cost_usd | 0.0 |
| mean_llm_calls | 31 |

| id | expected | got | ctx rel | grounded | faithful | halluc | viol recall | s |
|---|---|---|---|---|---|---|---|---|
| S01 | revise-and-recheck | specialist-review X | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 145.1 |
