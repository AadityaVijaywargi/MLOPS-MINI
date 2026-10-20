# Evaluation: real_nomod_part2

- run at: 2026-10-20T10:46:16.785086+00:00
- variant: v2
- api: http://api:8000

| metric | value |
|---|---|
| scenarios | 7 |
| errors | 0 |
| provider_degraded | 0 |
| scored | 7 |
| route_accuracy | 0.7143 |
| groundedness | 1.0 |
| context_relevance | 0.0 |
| faithfulness | 0.8435 |
| hallucination_rate | 0.0 |
| violation_recall | 0.0 |
| mean_latency_s | 46.4286 |
| mean_cost_usd | 0.0 |
| mean_llm_calls | 15.2857 |

| id | expected | got | ctx rel | grounded | faithful | halluc | viol recall | s |
|---|---|---|---|---|---|---|---|---|
| S09 | revise-and-recheck | specialist-review X | 0.0 | 1.0 | 0.3333333333333333 | 0.0 | 0.0 | 80.3 |
| S10 | revise-and-recheck | clear-for-submission X | 0.0 | 1.0 | 1.0 | 0.0 | 0.0 | 50.1 |
| S11 | specialist-review | specialist-review | None | 1.0 | 0.8571428571428571 | 0.0 | None | 20.1 |
| S12 | specialist-review | specialist-review | None | 1.0 | 1.0 | 0.0 | None | 38.1 |
| S13 | specialist-review | specialist-review | None | 1.0 | 1.0 | 0.0 | None | 16.1 |
| S14 | specialist-review | specialist-review | None | 1.0 | 0.7142857142857143 | 0.0 | None | 52.1 |
| S15 | specialist-review | specialist-review | None | 1.0 | 1.0 | 0.0 | None | 68.2 |
