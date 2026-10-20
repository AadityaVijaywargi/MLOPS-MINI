# Evaluation: real_nomod_part1_rerun0054

- run at: 2026-10-20T20:07:07.827906+00:00
- variant: v2
- api: http://api:8000

| metric | value |
|---|---|
| scenarios | 1 |
| errors | 0 |
| provider_degraded | 0 |
| scored | 1 |
| route_accuracy | 1.0 |
| groundedness | 1.0 |
| context_relevance | 1.0 |
| faithfulness | 1.0 |
| hallucination_rate | 0.0 |
| violation_recall | None |
| mean_latency_s | 177.0 |
| mean_cost_usd | 0.0 |
| mean_llm_calls | 27 |

| id | expected | got | ctx rel | grounded | faithful | halluc | viol recall | s |
|---|---|---|---|---|---|---|---|---|
| S06 | clear-for-submission | clear-for-submission | 1.0 | 1.0 | 1.0 | 0.0 | None | 177.0 |
