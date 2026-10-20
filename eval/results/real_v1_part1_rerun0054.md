# Evaluation: real_v1_part1_rerun0054

- run at: 2026-10-20T19:45:20.037589+00:00
- variant: v1
- api: http://api:8000

| metric | value |
|---|---|
| scenarios | 6 |
| errors | 0 |
| provider_degraded | 3 |
| scored | 3 |
| route_accuracy | 0.6667 |
| groundedness | 0.7778 |
| context_relevance | 1.0 |
| faithfulness | 0.7778 |
| hallucination_rate | 0.2222 |
| violation_recall | 0.0 |
| mean_latency_s | 236.3 |
| mean_cost_usd | 0.0 |
| mean_llm_calls | 18.6667 |

| id | expected | got | ctx rel | grounded | faithful | halluc | viol recall | s |
|---|---|---|---|---|---|---|---|---|
| S03 | revise-and-recheck | specialist-review (provider down, not scored) | 1.0 | None | None | None | 0.0 | 120.6 |
| S04 | revise-and-recheck | specialist-review (provider down, not scored) | 1.0 | 0.3333333333333333 | 1.0 | 0.6666666666666666 | 0.0 | 283.7 |
| S05 | revise-and-recheck | specialist-review X | 1.0 | 0.3333333333333333 | 1.0 | 0.6666666666666666 | 0.0 | 295.2 |
| S06 | clear-for-submission | clear-for-submission | 1.0 | 1.0 | 0.3333333333333333 | 0.0 | None | 245.0 |
| S07 | revise-and-recheck | specialist-review (provider down, not scored) | 1.0 | None | None | None | 0.0 | 120.4 |
| S08 | clear-for-submission | clear-for-submission | 1.0 | 1.0 | 1.0 | 0.0 | None | 168.7 |
