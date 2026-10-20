# Evaluation: real_v1_part1

- run at: 2026-10-20T18:00:44.542333+00:00
- variant: v1
- api: http://api:8000

| metric | value |
|---|---|
| scenarios | 8 |
| errors | 0 |
| provider_degraded | 6 |
| scored | 2 |
| route_accuracy | 0.5 |
| groundedness | 1.0 |
| context_relevance | 1.0 |
| faithfulness | 1.0 |
| hallucination_rate | 0.0 |
| violation_recall | 1.0 |
| mean_latency_s | 133.45 |
| mean_cost_usd | 0.0 |
| mean_llm_calls | 18.5 |

| id | expected | got | ctx rel | grounded | faithful | halluc | viol recall | s |
|---|---|---|---|---|---|---|---|---|
| S01 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 76.3 |
| S02 | clear-for-submission | specialist-review X | 1.0 | 1.0 | 1.0 | 0.0 | None | 190.6 |
| S03 | revise-and-recheck | specialist-review (provider down, not scored) | 1.0 | None | None | None | 0.0 | 36.2 |
| S04 | revise-and-recheck | specialist-review (provider down, not scored) | 1.0 | None | None | None | 0.0 | 2.0 |
| S05 | revise-and-recheck | specialist-review (provider down, not scored) | 1.0 | None | None | None | 0.0 | 2.0 |
| S06 | clear-for-submission | specialist-review (provider down, not scored) | 1.0 | None | None | None | None | 2.0 |
| S07 | revise-and-recheck | specialist-review (provider down, not scored) | 1.0 | None | None | None | 0.0 | 2.0 |
| S08 | clear-for-submission | specialist-review (provider down, not scored) | 0.5 | None | None | None | None | 2.0 |
