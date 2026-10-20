# Evaluation: real_v1

- run at: 2026-10-19T19:27:13.472051+00:00
- variant: v1
- api: http://api:8000

| metric | value |
|---|---|
| scenarios | 22 |
| errors | 0 |
| route_accuracy | 0.4545 |
| groundedness | 0.9378 |
| context_relevance | 0.9412 |
| faithfulness | 1.0 |
| hallucination_rate | 0.0622 |
| violation_recall | 0.4091 |
| mean_latency_s | 71.3136 |
| mean_cost_usd | 0.0 |
| mean_llm_calls | 14.4091 |

| id | expected | got | ctx rel | grounded | faithful | halluc | viol recall | s |
|---|---|---|---|---|---|---|---|---|
| S01 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 0.5 | 31.4 |
| S02 | clear-for-submission | specialist-review X | 1.0 | 1.0 | 1.0 | 0.0 | None | 66.1 |
| S03 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 53.6 |
| S04 | revise-and-recheck | revise-and-recheck | 1.0 | 0.4 | 1.0 | 0.6 | 1.0 | 164.8 |
| S05 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 52.6 |
| S06 | clear-for-submission | specialist-review X | 1.0 | 1.0 | 1.0 | 0.0 | None | 172.0 |
| S07 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 68.8 |
| S08 | clear-for-submission | specialist-review X | 1.0 | 1.0 | 1.0 | 0.0 | None | 86.4 |
| S09 | revise-and-recheck | specialist-review X | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 150.6 |
| S10 | revise-and-recheck | specialist-review X | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 74.4 |
| S11 | specialist-review | specialist-review | None | 1.0 | 1.0 | 0.0 | None | 90.3 |
| S12 | specialist-review | specialist-review | None | 1.0 | 1.0 | 0.0 | None | 105.0 |
| S13 | specialist-review | specialist-review | None | 0.6666666666666666 | 1.0 | 0.3333333333333333 | None | 165.9 |
| S14 | specialist-review | specialist-review | None | 1.0 | 1.0 | 0.0 | None | 89.0 |
| S15 | specialist-review | specialist-review | None | 1.0 | 1.0 | 0.0 | None | 119.5 |
| S16 | revise-and-recheck | specialist-review X | 1.0 | None | None | None | 0.0 | 61.0 |
| S17 | clear-for-submission | specialist-review X | 1.0 | None | None | None | None | 2.2 |
| S18 | revise-and-recheck | specialist-review X | 1.0 | None | None | None | 0.0 | 4.2 |
| S19 | revise-and-recheck | specialist-review X | 1.0 | None | None | None | 0.0 | 2.2 |
| S20 | clear-for-submission | specialist-review X | 1.0 | None | None | None | None | 2.3 |
| S21 | clear-for-submission | specialist-review X | 1.0 | None | None | None | None | 2.4 |
| S22 | revise-and-recheck | specialist-review X | 0.0 | None | None | None | 0.0 | 4.2 |
