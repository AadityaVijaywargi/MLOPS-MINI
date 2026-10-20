# Evaluation (L2, L3, L6)

## The set

`eval/scenarios.yaml` - 22 fixed scenarios, each with a full proposal (base + overrides),
the expected route, the gold clause ids that must be retrieved, the clause ids expected to be
found violated, and the verbatim corpus passage that supports the expected outcome. It
includes the section 4.1 reference case (`S01`, see `docs/reference_case.md`) and covers:

| Kind | Scenarios |
|---|---|
| clear-for-submission | S02, S06, S08, S17, S20, S21 |
| revise-and-recheck: setbacks | S05, S07, S19 (+ S01 via Table 9) |
| revise: FAR / coverage | S03, S04, S16, S18 |
| revise: height by road width | S01 |
| revise: use / dwelling-unit notes | S09, S10 |
| revise: high-rise road width (bye-law) | S22 |
| specialist-review: exemption / special regime | S11 (TDR), S12 (heritage), S13 (aerodrome) |
| specialist-review: outside corpus | S14 |
| specialist-review: prompt injection | S15 |

Run as a batch from the command line (inside the stack, so no local Python is needed):

```bash
docker compose --profile tools run --rm eval python -m bpc.evaluation.run_eval --label <name> [--variant v1|v2] [--only S01,S02]
docker compose --profile tools run --rm eval python -m bpc.evaluation.run_eval --compare eval/results/<a>.json eval/results/<b>.json
```

Results land in `eval/results/<label>.json` (per scenario, with run ids that can be
reconstructed via `/v1/runs/{id}/trace`) and `<label>.md`.

## Metrics and how each is computed

"TruLens or equivalent": the same four RAG-triad style metrics are computed
deterministically from the run trace instead of with an LLM judge, so they are cheap,
reproducible and cannot be gamed by the model being judged. They are measured on the
assessor's **first** answer that contains findings (before self-verification filtered it;
a hand-back for missing topics has no findings and is skipped), so they measure the model;
what is *returned* is verified by construction.

| Metric | Definition |
|---|---|
| **Groundedness** | citations whose quote is found verbatim (whitespace/punctuation-normalised) in the passage they cite, which must be a passage retrieved in this run / all citations |
| **Context relevance** | offline: gold clause ids present among the passages the research agent retrieved / gold clause ids (scenarios with gold). Online (no gold): share of the dossier's passages that a verified finding actually used |
| **Faithfulness** | findings with a numeric comparison whose status agrees with their own required/proposed values and comparison / findings with a numeric comparison |
| **Hallucination rate** | findings with an unresolvable provision id, a quote not in the passage, or a number that appears neither in the passage nor the proposal (nor follows from them via the stated derivation) / all findings |
| Route accuracy | runs whose route equals the expected route / runs |
| Violation recall | expected violated clause ids found violated / expected violated clause ids |

## Experiments

* **L2 prompt variants** - `assessor.findings@v1` (baseline: schema + rules) vs
  `assessor.findings@v2` (procedural: applicability first, explicit derivation, cumulative
  provisions, worked example). Same scenarios, same model, `--variant v1` / `--variant v2`.
* **L3 deliberate change** - the research agent's modifier-check step on vs off
  (`MODIFIER_SEARCH_ENABLED`), all four metrics before and after.

Real-model arms run with `--reuse-model-cache`: the whole-run cache is bypassed, but model
responses for unchanged steps are replayed from the gateway's response cache. Because the
research loop's prompts do not depend on the assessor prompt variant, the v2 arm replays the
v1 arm's research loop call for call and only the assessor's calls are new. That makes the
comparison a controlled one (same dossier, only the variable under test differs) and keeps a
22-scenario arm within a free-tier daily quota (INC-005).

Results: see `eval/results/` and the summary in `docs/report.md`.

## Online scoring (L6)

`ONLINE_EVAL_SAMPLE_RATE` (25 %) of live runs are scored by the assessor worker with the same
definitions (context relevance in its online form) and written to `quality_scores`; the
`online_quality_score{metric}` gauge drives the Grafana "Online quality of sampled live runs"
panel and `GET /v1/quality?hours=24` returns the hourly series. Caller feedback
(`POST /v1/runs/{id}/feedback`) is persisted and aggregated by route at
`GET /v1/feedback/summary`.
