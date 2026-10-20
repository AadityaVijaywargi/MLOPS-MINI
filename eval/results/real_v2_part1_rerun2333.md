# Evaluation: real_v2_part1_rerun2333

- run at: 2026-10-20T18:13:24.079302+00:00
- variant: v2
- api: http://api:8000

| metric | value |
|---|---|
| scenarios | 8 |
| errors | 0 |
| provider_degraded | 7 |
| scored | 1 |
| route_accuracy | 1.0 |
| groundedness | 1.0 |
| context_relevance | 1.0 |
| faithfulness | 1.0 |
| hallucination_rate | 0.0 |
| violation_recall | 1.0 |
| mean_latency_s | 228.7 |
| mean_cost_usd | 0.0 |
| mean_llm_calls | 29 |

| id | expected | got | ctx rel | grounded | faithful | halluc | viol recall | s |
|---|---|---|---|---|---|---|---|---|
| S01 | revise-and-recheck | specialist-review (provider down, not scored) | 1.0 | None | None | None | 0.0 | 2.1 |
| S02 | clear-for-submission | specialist-review (provider down, not scored) | 1.0 | None | None | None | None | 2.0 |
| S03 | revise-and-recheck | specialist-review (provider down, not scored) | 1.0 | None | None | None | 0.0 | 2.0 |
| S04 | revise-and-recheck | specialist-review (provider down, not scored) | 1.0 | None | None | None | 0.0 | 2.0 |
| S05 | revise-and-recheck | specialist-review (provider down, not scored) | 1.0 | None | None | None | 0.0 | 2.0 |
| S06 | clear-for-submission | specialist-review (provider down, not scored) | 1.0 | None | None | None | None | 2.0 |
| S07 | revise-and-recheck | revise-and-recheck | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 228.7 |
| S08 | clear-for-submission | specialist-review (provider down, not scored) | 1.0 | 1.0 | 1.0 | 0.0 | None | 240.6 |
