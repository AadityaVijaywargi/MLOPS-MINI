# Evaluation: real_nomod_part1_rerun2333

- run at: 2026-10-20T18:31:04.136362+00:00
- variant: v2
- api: http://api:8000

| metric | value |
|---|---|
| scenarios | 8 |
| errors | 0 |
| provider_degraded | 1 |
| scored | 7 |
| route_accuracy | 0.5714 |
| groundedness | 0.9286 |
| context_relevance | 1.0 |
| faithfulness | 0.8155 |
| hallucination_rate | 0.0918 |
| violation_recall | 0.6 |
| mean_latency_s | 131.2714 |
| mean_cost_usd | 0.0 |
| mean_llm_calls | 17.2857 |

| id | expected | got | ctx rel | grounded | faithful | halluc | viol recall | s |
|---|---|---|---|---|---|---|---|---|
| S01 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 0.42857142857142855 | 0.0 | 1.0 | 168.5 |
| S02 | clear-for-submission | clear-for-submission | 1.0 | 1.0 | 0.875 | 0.0 | None | 122.3 |
| S03 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 96.3 |
| S04 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 0.8333333333333334 | 0.0 | 1.0 | 88.2 |
| S05 | revise-and-recheck | specialist-review X | 1.0 | 1.0 | 0.5714285714285714 | 0.14285714285714285 | 0.0 | 92.3 |
| S06 | clear-for-submission | specialist-review (provider down, not scored) | 1.0 | None | None | None | None | 120.4 |
| S07 | revise-and-recheck | clear-for-submission X | 1.0 | 0.5 | 1.0 | 0.5 | 0.0 | 168.7 |
| S08 | clear-for-submission | specialist-review X | 1.0 | 1.0 | 1.0 | 0.0 | None | 182.6 |
