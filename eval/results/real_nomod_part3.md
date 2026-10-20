# Evaluation: real_nomod_part3

- run at: 2026-10-20T17:01:22.613574+00:00
- variant: v2
- api: http://api:8000

| metric | value |
|---|---|
| scenarios | 7 |
| errors | 0 |
| provider_degraded | 0 |
| scored | 7 |
| route_accuracy | 0.5714 |
| groundedness | 1.0 |
| context_relevance | 0.8571 |
| faithfulness | 1.0 |
| hallucination_rate | 0.0 |
| violation_recall | 0.75 |
| mean_latency_s | 251.4429 |
| mean_cost_usd | 0.0 |
| mean_llm_calls | 19.8571 |

| id | expected | got | ctx rel | grounded | faithful | halluc | viol recall | s |
|---|---|---|---|---|---|---|---|---|
| S16 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 405.0 |
| S17 | clear-for-submission | specialist-review X | 1.0 | 1.0 | 1.0 | 0.0 | None | 276.6 |
| S18 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 212.5 |
| S19 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 136.3 |
| S20 | clear-for-submission | specialist-review X | 0.5 | 1.0 | 1.0 | 0.0 | None | 557.3 |
| S21 | clear-for-submission | clear-for-submission | 1.0 | 1.0 | 1.0 | 0.0 | None | 152.3 |
| S22 | revise-and-recheck | clear-for-submission X | 0.5 | 1.0 | 1.0 | 0.0 | 0.0 | 20.1 |
