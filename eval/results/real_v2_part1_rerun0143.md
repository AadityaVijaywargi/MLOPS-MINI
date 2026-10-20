# Evaluation: real_v2_part1_rerun0143

- run at: 2026-10-20T20:18:54.950563+00:00
- variant: v2
- api: http://api:8000

| metric | value |
|---|---|
| scenarios | 2 |
| errors | 0 |
| provider_degraded | 0 |
| scored | 2 |
| route_accuracy | 1.0 |
| groundedness | 1.0 |
| context_relevance | 1.0 |
| faithfulness | 1.0 |
| hallucination_rate | 0.0 |
| violation_recall | 1.0 |
| mean_latency_s | 77.25 |
| mean_cost_usd | 0.0 |
| mean_llm_calls | 27 |

| id | expected | got | ctx rel | grounded | faithful | halluc | viol recall | s |
|---|---|---|---|---|---|---|---|---|
| S04 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 92.3 |
| S08 | clear-for-submission | clear-for-submission | 1.0 | 1.0 | 1.0 | 0.0 | None | 62.2 |
