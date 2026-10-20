# Evaluation: real_v2_part1

- run at: 2026-10-20T18:01:04.011841+00:00
- variant: v2
- api: http://api:8000

| metric | value |
|---|---|
| scenarios | 8 |
| errors | 0 |
| provider_degraded | 8 |
| scored | 0 |
| route_accuracy | None |
| groundedness | None |
| context_relevance | None |
| faithfulness | None |
| hallucination_rate | None |
| violation_recall | None |
| mean_latency_s | None |
| mean_cost_usd | None |
| mean_llm_calls | None |

| id | expected | got | ctx rel | grounded | faithful | halluc | viol recall | s |
|---|---|---|---|---|---|---|---|---|
| S01 | revise-and-recheck | specialist-review (provider down, not scored) | 1.0 | None | None | None | 0.0 | 2.0 |
| S02 | clear-for-submission | specialist-review (provider down, not scored) | 1.0 | None | None | None | None | 2.1 |
| S03 | revise-and-recheck | specialist-review (provider down, not scored) | 1.0 | None | None | None | 0.0 | 2.0 |
| S04 | revise-and-recheck | specialist-review (provider down, not scored) | 1.0 | None | None | None | 0.0 | 2.0 |
| S05 | revise-and-recheck | specialist-review (provider down, not scored) | 1.0 | None | None | None | 0.0 | 2.0 |
| S06 | clear-for-submission | specialist-review (provider down, not scored) | 1.0 | None | None | None | None | 2.0 |
| S07 | revise-and-recheck | specialist-review (provider down, not scored) | 1.0 | None | None | None | 0.0 | 2.0 |
| S08 | clear-for-submission | specialist-review (provider down, not scored) | 1.0 | None | None | None | None | 2.0 |
