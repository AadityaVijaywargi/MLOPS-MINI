# Evaluation: real_S01_select

- run at: 2026-10-19T18:59:05.410218+00:00
- variant: v1
- api: http://api:8000

| metric | value |
|---|---|
| scenarios | 1 |
| errors | 0 |
| route_accuracy | 1.0 |
| groundedness | 1.0 |
| context_relevance | 1.0 |
| faithfulness | 1.0 |
| hallucination_rate | 0.25 |
| violation_recall | 0.5 |
| mean_latency_s | 35.5 |
| mean_cost_usd | 0.0 |
| mean_llm_calls | 11 |

| id | expected | got | ctx rel | grounded | faithful | halluc | viol recall | s |
|---|---|---|---|---|---|---|---|---|
| S01 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.25 | 0.5 | 35.5 |
