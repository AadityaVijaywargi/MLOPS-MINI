# Evaluation: real_v1_part2

- run at: 2026-10-20T10:26:13.296029+00:00
- variant: v1
- api: http://api:8000

| metric | value |
|---|---|
| scenarios | 7 |
| errors | 0 |
| provider_degraded | 0 |
| scored | 7 |
| route_accuracy | 0.7143 |
| groundedness | 0.8801 |
| context_relevance | 0.0 |
| faithfulness | 1.0 |
| hallucination_rate | 0.1199 |
| violation_recall | 0.0 |
| mean_latency_s | 91.6714 |
| mean_cost_usd | 0.0 |
| mean_llm_calls | 18.5714 |

| id | expected | got | ctx rel | grounded | faithful | halluc | viol recall | s |
|---|---|---|---|---|---|---|---|---|
| S09 | revise-and-recheck | specialist-review X | 0.0 | 1.0 | 1.0 | 0.0 | 0.0 | 76.2 |
| S10 | revise-and-recheck | clear-for-submission X | 0.0 | 0.8571428571428571 | 1.0 | 0.14285714285714285 | 0.0 | 126.3 |
| S11 | specialist-review | specialist-review | None | 1.0 | 1.0 | 0.0 | None | 104.3 |
| S12 | specialist-review | specialist-review | None | 0.875 | 1.0 | 0.125 | None | 66.2 |
| S13 | specialist-review | specialist-review | None | 1.0 | 1.0 | 0.0 | None | 72.2 |
| S14 | specialist-review | specialist-review | None | 1.0 | 1.0 | 0.0 | None | 104.3 |
| S15 | specialist-review | specialist-review | None | 0.42857142857142855 | 1.0 | 0.5714285714285714 | None | 92.2 |
