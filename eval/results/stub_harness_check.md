# Evaluation: stub_harness_check

- run at: 2026-10-19T15:49:05.043227+00:00
- variant: default
- api: http://api:8000

| metric | value |
|---|---|
| scenarios | 22 |
| errors | 0 |
| route_accuracy | 0.2273 |
| groundedness | 1.0 |
| context_relevance | 0.9706 |
| faithfulness | None |
| hallucination_rate | 0.0 |
| violation_recall | 0.0 |
| mean_latency_s | 19.95 |
| mean_cost_usd | 0.0 |
| mean_llm_calls | 13 |

| id | expected | got | ctx rel | grounded | faithful | halluc | viol recall | s |
|---|---|---|---|---|---|---|---|---|
| S01 | revise-and-recheck | specialist-review X | 1.0 | 1.0 | None | 0.0 | 0.0 | 20.1 |
| S02 | clear-for-submission | specialist-review X | 1.0 | 1.0 | None | 0.0 | None | 18.1 |
| S03 | revise-and-recheck | specialist-review X | 1.0 | 1.0 | None | 0.0 | 0.0 | 20.1 |
| S04 | revise-and-recheck | specialist-review X | 1.0 | 1.0 | None | 0.0 | 0.0 | 20.2 |
| S05 | revise-and-recheck | specialist-review X | 1.0 | 1.0 | None | 0.0 | 0.0 | 20.2 |
| S06 | clear-for-submission | specialist-review X | 1.0 | 1.0 | None | 0.0 | None | 20.1 |
| S07 | revise-and-recheck | specialist-review X | 1.0 | 1.0 | None | 0.0 | 0.0 | 20.2 |
| S08 | clear-for-submission | specialist-review X | 1.0 | 1.0 | None | 0.0 | None | 22.5 |
| S09 | revise-and-recheck | specialist-review X | 1.0 | 1.0 | None | 0.0 | 0.0 | 16.1 |
| S10 | revise-and-recheck | specialist-review X | 1.0 | 1.0 | None | 0.0 | 0.0 | 20.1 |
| S11 | specialist-review | specialist-review | None | 1.0 | None | 0.0 | None | 22.1 |
| S12 | specialist-review | specialist-review | None | 1.0 | None | 0.0 | None | 18.1 |
| S13 | specialist-review | specialist-review | None | 1.0 | None | 0.0 | None | 20.1 |
| S14 | specialist-review | specialist-review | None | 1.0 | None | 0.0 | None | 20.1 |
| S15 | specialist-review | specialist-review | None | 1.0 | None | 0.0 | None | 22.1 |
| S16 | revise-and-recheck | specialist-review X | 1.0 | 1.0 | None | 0.0 | 0.0 | 20.1 |
| S17 | clear-for-submission | specialist-review X | 1.0 | 1.0 | None | 0.0 | None | 20.1 |
| S18 | revise-and-recheck | specialist-review X | 1.0 | 1.0 | None | 0.0 | 0.0 | 20.1 |
| S19 | revise-and-recheck | specialist-review X | 1.0 | 1.0 | None | 0.0 | 0.0 | 20.1 |
| S20 | clear-for-submission | specialist-review X | 1.0 | 1.0 | None | 0.0 | None | 20.1 |
| S21 | clear-for-submission | specialist-review X | 1.0 | 1.0 | None | 0.0 | None | 18.1 |
| S22 | revise-and-recheck | specialist-review X | 0.5 | 1.0 | None | 0.0 | 0.0 | 20.1 |
