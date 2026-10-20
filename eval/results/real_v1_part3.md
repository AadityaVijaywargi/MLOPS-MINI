# Evaluation: real_v1_part3

- run at: 2026-10-20T15:36:17.925240+00:00
- variant: v1
- api: http://api:8000

| metric | value |
|---|---|
| scenarios | 7 |
| errors | 0 |
| provider_degraded | 5 |
| scored | 2 |
| route_accuracy | 0.0 |
| groundedness | 0.4792 |
| context_relevance | 0.75 |
| faithfulness | 1.0 |
| hallucination_rate | 0.5208 |
| violation_recall | 0.0 |
| mean_latency_s | 611.15 |
| mean_cost_usd | 0.0 |
| mean_llm_calls | 21.5 |

| id | expected | got | ctx rel | grounded | faithful | halluc | viol recall | s |
|---|---|---|---|---|---|---|---|---|
| S16 | revise-and-recheck | specialist-review (provider down, not scored) | 1.0 | None | None | None | 0.0 | 420.8 |
| S17 | clear-for-submission | specialist-review X | 1.0 | 0.3333333333333333 | 1.0 | 0.6666666666666666 | None | 869.6 |
| S18 | revise-and-recheck | specialist-review (provider down, not scored) | 1.0 | None | None | None | 0.0 | 420.8 |
| S19 | revise-and-recheck | specialist-review (provider down, not scored) | 1.0 | None | None | None | 0.0 | 420.8 |
| S20 | clear-for-submission | specialist-review (provider down, not scored) | 1.0 | None | None | None | None | 420.9 |
| S21 | clear-for-submission | specialist-review (provider down, not scored) | 1.0 | None | None | None | None | 420.8 |
| S22 | revise-and-recheck | clear-for-submission X | 0.5 | 0.625 | 1.0 | 0.375 | 0.0 | 352.7 |
