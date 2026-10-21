# Evaluation: real_nomod_part3_rerun1347

- run at: 2026-10-21T08:45:08.592380+00:00
- variant: v2
- api: http://api:8000

| metric | value |
|---|---|
| scenarios | 6 |
| errors | 0 |
| provider_degraded | 0 |
| scored | 6 |
| route_accuracy | 1.0 |
| groundedness | 1.0 |
| context_relevance | 1.0 |
| faithfulness | 1.0 |
| hallucination_rate | 0.0 |
| violation_recall | 1.0 |
| mean_latency_s | 76.0 |
| mean_cost_usd | 0.0 |
| mean_llm_calls | 20.8333 |

| id | expected | got | ctx rel | grounded | faithful | halluc | viol recall | s |
|---|---|---|---|---|---|---|---|---|
| S16 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 78.4 |
| S17 | clear-for-submission | clear-for-submission | 1.0 | 1.0 | 1.0 | 0.0 | None | 120.5 |
| S18 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 166.6 |
| S19 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 18.1 |
| S20 | clear-for-submission | clear-for-submission | 1.0 | 1.0 | 1.0 | 0.0 | None | 48.3 |
| S21 | clear-for-submission | clear-for-submission | 1.0 | 1.0 | 1.0 | 0.0 | None | 24.1 |
