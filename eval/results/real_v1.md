# Evaluation: real_v1

- run at: 2026-10-21T08:45:48.984474+00:00
- variant: v1
- api: merged
- merged from: real_v1_part1.json, real_v1_part1_rerun0054.json, real_v1_part1_rerun0143.json, real_v1_part1_rerun2333.json, real_v1_part2.json, real_v1_part3.json, real_v1_part3_rerun1347.json

| metric | value |
|---|---|
| scenarios | 22 |
| errors | 0 |
| provider_degraded | 0 |
| scored | 22 |
| route_accuracy | 0.7273 |
| groundedness | 0.908 |
| context_relevance | 0.8529 |
| faithfulness | 0.9697 |
| hallucination_rate | 0.092 |
| violation_recall | 0.5455 |
| mean_latency_s | 124.6818 |
| mean_cost_usd | 0.0 |
| mean_llm_calls | 18.5 |

| id | expected | got | ctx rel | grounded | faithful | halluc | viol recall | s |
|---|---|---|---|---|---|---|---|---|
| S01 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 76.3 |
| S02 | clear-for-submission | specialist-review X | 1.0 | 1.0 | 1.0 | 0.0 | None | 190.6 |
| S03 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 30.2 |
| S04 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 54.2 |
| S05 | revise-and-recheck | specialist-review X | 1.0 | 0.3333333333333333 | 1.0 | 0.6666666666666666 | 0.0 | 295.2 |
| S06 | clear-for-submission | clear-for-submission | 1.0 | 1.0 | 0.3333333333333333 | 0.0 | None | 245.0 |
| S07 | revise-and-recheck | specialist-review X | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 82.3 |
| S08 | clear-for-submission | clear-for-submission | 1.0 | 1.0 | 1.0 | 0.0 | None | 168.7 |
| S09 | revise-and-recheck | specialist-review X | 0.0 | 1.0 | 1.0 | 0.0 | 0.0 | 76.2 |
| S10 | revise-and-recheck | clear-for-submission X | 0.0 | 0.8571428571428571 | 1.0 | 0.14285714285714285 | 0.0 | 126.3 |
| S11 | specialist-review | specialist-review | None | 1.0 | 1.0 | 0.0 | None | 104.3 |
| S12 | specialist-review | specialist-review | None | 0.875 | 1.0 | 0.125 | None | 66.2 |
| S13 | specialist-review | specialist-review | None | 1.0 | 1.0 | 0.0 | None | 72.2 |
| S14 | specialist-review | specialist-review | None | 1.0 | 1.0 | 0.0 | None | 104.3 |
| S15 | specialist-review | specialist-review | None | 0.42857142857142855 | 1.0 | 0.5714285714285714 | None | 92.2 |
| S16 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 84.4 |
| S17 | clear-for-submission | clear-for-submission | 1.0 | 0.8571428571428571 | 1.0 | 0.14285714285714285 | None | 172.9 |
| S18 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 68.3 |
| S19 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 110.5 |
| S20 | clear-for-submission | clear-for-submission | 1.0 | 1.0 | 1.0 | 0.0 | None | 66.3 |
| S21 | clear-for-submission | clear-for-submission | 1.0 | 1.0 | 1.0 | 0.0 | None | 103.7 |
| S22 | revise-and-recheck | clear-for-submission X | 0.5 | 0.625 | 1.0 | 0.375 | 0.0 | 352.7 |
