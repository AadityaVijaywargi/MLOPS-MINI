# Evaluation: real_v2_part3

- run at: 2026-10-20T16:31:41.696505+00:00
- variant: v2
- api: http://api:8000

| metric | value |
|---|---|
| scenarios | 7 |
| errors | 0 |
| provider_degraded | 3 |
| scored | 4 |
| route_accuracy | 0.75 |
| groundedness | 1.0 |
| context_relevance | 0.875 |
| faithfulness | 0.9643 |
| hallucination_rate | 0.0 |
| violation_recall | 0.6667 |
| mean_latency_s | 412.4 |
| mean_cost_usd | 0.0 |
| mean_llm_calls | 20.5 |

| id | expected | got | ctx rel | grounded | faithful | halluc | viol recall | s |
|---|---|---|---|---|---|---|---|---|
| S16 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 631.4 |
| S17 | clear-for-submission | specialist-review (provider down, not scored) | 1.0 | None | None | None | None | 420.9 |
| S18 | revise-and-recheck | specialist-review (provider down, not scored) | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 829.8 |
| S19 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 290.6 |
| S20 | clear-for-submission | clear-for-submission | 1.0 | 1.0 | 1.0 | 0.0 | None | 410.9 |
| S21 | clear-for-submission | specialist-review (provider down, not scored) | 1.0 | None | None | None | None | 420.8 |
| S22 | revise-and-recheck | clear-for-submission X | 0.5 | 1.0 | 0.8571428571428571 | 0.0 | 0.0 | 316.7 |
