# Evaluation: real_v2_part2

- run at: 2026-10-20T10:40:22.251006+00:00
- variant: v2
- api: http://api:8000

| metric | value |
|---|---|
| scenarios | 7 |
| errors | 0 |
| provider_degraded | 0 |
| scored | 7 |
| route_accuracy | 0.8571 |
| groundedness | 1.0 |
| context_relevance | 1.0 |
| faithfulness | 0.8163 |
| hallucination_rate | 0.0 |
| violation_recall | 0.5 |
| mean_latency_s | 60.7429 |
| mean_cost_usd | 0.0 |
| mean_llm_calls | 16.4286 |

| id | expected | got | ctx rel | grounded | faithful | halluc | viol recall | s |
|---|---|---|---|---|---|---|---|---|
| S09 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 0.42857142857142855 | 0.0 | 1.0 | 20.1 |
| S10 | revise-and-recheck | clear-for-submission X | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 108.3 |
| S11 | specialist-review | specialist-review | None | 1.0 | 0.8571428571428571 | 0.0 | None | 66.2 |
| S12 | specialist-review | specialist-review | None | 1.0 | 0.42857142857142855 | 0.0 | None | 20.1 |
| S13 | specialist-review | specialist-review | None | 1.0 | 1.0 | 0.0 | None | 56.1 |
| S14 | specialist-review | specialist-review | None | 1.0 | 1.0 | 0.0 | None | 68.2 |
| S15 | specialist-review | specialist-review | None | 1.0 | 1.0 | 0.0 | None | 86.2 |
