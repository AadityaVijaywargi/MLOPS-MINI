# Evaluation: real_nomod

- run at: 2026-10-21T08:45:50.951948+00:00
- variant: v2
- api: merged
- merged from: real_nomod_part1.json, real_nomod_part1_rerun0054.json, real_nomod_part1_rerun2333.json, real_nomod_part2.json, real_nomod_part3.json, real_nomod_part3_rerun1347.json

| metric | value |
|---|---|
| scenarios | 22 |
| errors | 0 |
| provider_degraded | 0 |
| scored | 22 |
| route_accuracy | 0.7273 |
| groundedness | 0.9773 |
| context_relevance | 0.8529 |
| faithfulness | 0.8915 |
| hallucination_rate | 0.0292 |
| violation_recall | 0.5455 |
| mean_latency_s | 86.2273 |
| mean_cost_usd | 0.0 |
| mean_llm_calls | 17.5909 |

| id | expected | got | ctx rel | grounded | faithful | halluc | viol recall | s |
|---|---|---|---|---|---|---|---|---|
| S01 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 0.42857142857142855 | 0.0 | 1.0 | 168.5 |
| S02 | clear-for-submission | clear-for-submission | 1.0 | 1.0 | 0.875 | 0.0 | None | 122.3 |
| S03 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 96.3 |
| S04 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 0.8333333333333334 | 0.0 | 1.0 | 88.2 |
| S05 | revise-and-recheck | specialist-review X | 1.0 | 1.0 | 0.5714285714285714 | 0.14285714285714285 | 0.0 | 92.3 |
| S06 | clear-for-submission | clear-for-submission | 1.0 | 1.0 | 1.0 | 0.0 | None | 177.0 |
| S07 | revise-and-recheck | clear-for-submission X | 1.0 | 0.5 | 1.0 | 0.5 | 0.0 | 168.7 |
| S08 | clear-for-submission | specialist-review X | 1.0 | 1.0 | 1.0 | 0.0 | None | 182.6 |
| S09 | revise-and-recheck | specialist-review X | 0.0 | 1.0 | 0.3333333333333333 | 0.0 | 0.0 | 80.3 |
| S10 | revise-and-recheck | clear-for-submission X | 0.0 | 1.0 | 1.0 | 0.0 | 0.0 | 50.1 |
| S11 | specialist-review | specialist-review | None | 1.0 | 0.8571428571428571 | 0.0 | None | 20.1 |
| S12 | specialist-review | specialist-review | None | 1.0 | 1.0 | 0.0 | None | 38.1 |
| S13 | specialist-review | specialist-review | None | 1.0 | 1.0 | 0.0 | None | 16.1 |
| S14 | specialist-review | specialist-review | None | 1.0 | 0.7142857142857143 | 0.0 | None | 52.1 |
| S15 | specialist-review | specialist-review | None | 1.0 | 1.0 | 0.0 | None | 68.2 |
| S16 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 78.4 |
| S17 | clear-for-submission | clear-for-submission | 1.0 | 1.0 | 1.0 | 0.0 | None | 120.5 |
| S18 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 166.6 |
| S19 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 18.1 |
| S20 | clear-for-submission | clear-for-submission | 1.0 | 1.0 | 1.0 | 0.0 | None | 48.3 |
| S21 | clear-for-submission | clear-for-submission | 1.0 | 1.0 | 1.0 | 0.0 | None | 24.1 |
| S22 | revise-and-recheck | clear-for-submission X | 0.5 | 1.0 | 1.0 | 0.0 | 0.0 | 20.1 |
