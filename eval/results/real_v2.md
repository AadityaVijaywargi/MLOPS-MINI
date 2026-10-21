# Evaluation: real_v2

- run at: 2026-10-21T08:45:50.054924+00:00
- variant: v2
- api: merged
- merged from: real_v2_part1.json, real_v2_part1_rerun0054.json, real_v2_part1_rerun0143.json, real_v2_part1_rerun2333.json, real_v2_part2.json, real_v2_part3.json, real_v2_part3_rerun1347.json

| metric | value |
|---|---|
| scenarios | 22 |
| errors | 0 |
| provider_degraded | 0 |
| scored | 22 |
| route_accuracy | 0.8636 |
| groundedness | 1.0 |
| context_relevance | 0.9706 |
| faithfulness | 0.9069 |
| hallucination_rate | 0.0 |
| violation_recall | 0.8182 |
| mean_latency_s | 116.1455 |
| mean_cost_usd | 0.0 |
| mean_llm_calls | 19.5455 |

| id | expected | got | ctx rel | grounded | faithful | halluc | viol recall | s |
|---|---|---|---|---|---|---|---|---|
| S01 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 130.5 |
| S02 | clear-for-submission | clear-for-submission | 1.0 | 1.0 | 1.0 | 0.0 | None | 138.6 |
| S03 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 64.3 |
| S04 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 92.3 |
| S05 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 0.8571428571428571 | 0.0 | 1.0 | 269.3 |
| S06 | clear-for-submission | clear-for-submission | 1.0 | 1.0 | 1.0 | 0.0 | None | 251.0 |
| S07 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 228.7 |
| S08 | clear-for-submission | clear-for-submission | 1.0 | 1.0 | 1.0 | 0.0 | None | 62.2 |
| S09 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 0.42857142857142855 | 0.0 | 1.0 | 20.1 |
| S10 | revise-and-recheck | clear-for-submission X | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 108.3 |
| S11 | specialist-review | specialist-review | None | 1.0 | 0.8571428571428571 | 0.0 | None | 66.2 |
| S12 | specialist-review | specialist-review | None | 1.0 | 0.42857142857142855 | 0.0 | None | 20.1 |
| S13 | specialist-review | specialist-review | None | 1.0 | 1.0 | 0.0 | None | 56.1 |
| S14 | specialist-review | specialist-review | None | 1.0 | 1.0 | 0.0 | None | 68.2 |
| S15 | specialist-review | specialist-review | None | 1.0 | 1.0 | 0.0 | None | 86.2 |
| S16 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 0.6666666666666666 | 0.0 | 1.0 | 132.6 |
| S17 | clear-for-submission | specialist-review X | 1.0 | 1.0 | 1.0 | 0.0 | None | 120.4 |
| S18 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 126.5 |
| S19 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 66.3 |
| S20 | clear-for-submission | clear-for-submission | 1.0 | 1.0 | 1.0 | 0.0 | None | 44.2 |
| S21 | clear-for-submission | clear-for-submission | 1.0 | 1.0 | 0.8571428571428571 | 0.0 | None | 86.4 |
| S22 | revise-and-recheck | clear-for-submission X | 0.5 | 1.0 | 0.8571428571428571 | 0.0 | 0.0 | 316.7 |
