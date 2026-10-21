# L3 Modifier-Step Analysis: Secondary Reflection vs Single-Pass Retrieval

- **Author / Teammate:** Friend 3 (Aarav Yuval B G, SRN: PES1UG24AM004)
- **Evaluation Set:** Slice 3 (Scenarios S16–S22) and Aggregate Slices 2 & 3
- **Model:** the team's agreed model via its OpenAI-compatible endpoint (shared privately, D4)
- **Configuration Variable:** `MODIFIER_SEARCH_ENABLED=true` (Prompt v2) vs `MODIFIER_SEARCH_ENABLED=false` (No-Mod)
- **Execution Logs:** `eval/results/real_v2_part3.json` vs `eval/results/real_nomod_part3.json`

---

## 0. Final Result After the Slice 3 Reruns (2026-10-21)

The sections below analyse the first slice 3 run, where only 4 scenarios could be scored in both
arms. S16-S21 were then rerun in all three arms on one machine (`real_*_part3_rerun1347`). All 22
scenarios are now scored in every arm, and the merged table is `eval/results/compare_real_v2_vs_real_nomod.md`:

| metric | modifier on (v2) | modifier off | delta |
|---|---|---|---|
| route accuracy | **0.8636 (19/22)** | 0.7273 (16/22) | -0.136 |
| violation recall | **0.8182** | 0.5455 | -0.273 |
| context relevance | **0.9706** | 0.8529 | -0.118 |
| groundedness | **1.0000** | 0.9773 | -0.023 |
| hallucination rate | **0.0000** | 0.0292 | +0.029 |
| mean latency | 116.1 s | **86.2 s** | -29.9 s |
| mean LLM calls | 19.5 | **17.6** | -2.0 |

The modifier step still pays off overall, but the gain comes from slices 1 and 2. Turning it off
breaks S05, S07, S08 and S09, and S09 and S10 lose `ZR2015:T10:ii.c`. In the rerun, slice 3 shows no
benefit: with the modifier off, **S20 retrieved `ZR2015:T10:ii.b` and routed correctly**, so the S20
regression analysed in section 3 did not reproduce. S17 went the other way: with the modifier on
it escalated to `specialist-review` (no verified height finding). Slice 3 route accuracy is 0.714 with the
modifier on and 0.857 with it off.

---

## 1. Executive Summary

Requirement **L3** mandates evaluating the system with a deliberate architectural change to determine its impact on the quality triad (groundedness, context relevance, faithfulness), hallucination rate, route accuracy, and operational cost.

In our multi-agent compliance service, municipal regulations exhibit **non-local requirement interactions**:
- A primary rule (e.g. Setback Table 8 or FAR Table 10) sets baseline permissions based on plot size and road width.
- A secondary modifier clause located in a different chapter, or printed as an unindexed footnote, imposes overriding caps (e.g., Table 10 Note (ii)(b) restricting height to 11.5 m on roads $< 9.0\text{ m}$).

To solve this, the **Research Agent** (`researcher`) incorporates an agentic **Modifier Check Step** (implemented in `src/bpc/agents/researcher/modifier.py`):
1. When the agent declares primary research complete, the system inspects the recorded provisions.
2. It detects variables that are subject to overriding caps under municipal bye-laws (e.g., building height vs. road width, plot depth vs. setbacks, high-rise fire buffers).
3. Derived search queries targeting these modifier provisions are generated and injected back into the LangGraph tool loop.
4. The tool loop resumes, retrieving and recording cross-referenced provisions before the final dossier is committed to the Assessment Agent.

In this experiment, we ablated this mechanism by toggling `MODIFIER_SEARCH_ENABLED=false`.

---

## 2. Quantitative Empirical Results & Provider Degradation Audit

### Slice 3 Scenarios Audit:
- **`real_v1_part3`:** 2 scored (`S17`, `S22`), **5 provider degraded** (`S16`, `S18`, `S19`, `S20`, `S21`) due to upstream Gemini free-tier rate limits.
- **`real_v2_part3`:** 4 scored (`S16`, `S19`, `S20`, `S22`), **3 provider degraded** (`S17`, `S18`, `S21`).
- **`real_nomod_part3`:** **All 7 scored** (`S16` through `S22`), 0 provider degraded.

Per evaluation protocol, provider-degraded runs reflect upstream infrastructure throttling rather than system reasoning quality and are excluded from metric scoring. To prevent sample asymmetry from confounding the comparison, we report both the raw file outputs and the **strictly paired, apples-to-apples comparison on the common non-degraded subset**.

### Slice 3 Strictly Paired Comparison ($n = 4$: S16, S19, S20, S22)

Evaluated under identical environmental conditions with `--reuse-model-cache`:

| Metric | Real v2 (Modifier On, $n=4$) | Real No-Mod (Modifier Off, $n=4$) | Delta (Paired) | Relative Impact |
|---|---|---|---|---|
| **Route Accuracy** | **0.7500 (3/4)** | 0.5000 (2/4) | **-0.2500** | **-33.3% relative drop** (-25.0 percentage points) |
| **Context Relevance** | **0.8750** | 0.7500 | **-0.1250** | **-12.5 percentage points** |
| **Groundedness** | **1.0000** | **1.0000** | 0.0000 | Perfect verbatim quoting maintained |
| **Faithfulness** | 0.9643 | **1.0000** | +0.0357 | Arithmetic valid on retrieved subset |
| **Hallucination Rate** | **0.0000** | **0.0000** | 0.0000 | Zero hallucinated citations |
| **Violation Recall** | 0.6667 | 0.6667 | 0.0000 | Violations recalled identically on $n=4$ |
| **Mean Latency** | 412.4 s | **279.7 s** | **-132.7 s** | **32.2% faster execution** |
| **Mean LLM Calls** | 20.5 calls | 21.0 calls | +0.5 calls | Comparable model call count |

*(Reference Raw Aggregates: `real_v2_part3` raw scored $n=4$ route accuracy = 0.7500; `real_nomod_part3` raw scored $n=7$ route accuracy = 0.5714).*

---

### Cross-Slice Aggregation (Slices 2 & 3 Strictly Paired, $n=11$)

In Slice 2 (S09–S15, Friend 2), all 7 scenarios completed without degradation in both arms. Combining those 7 scenarios with the 4 non-degraded Slice 3 scenarios yields **11 strictly comparable, paired scenarios** across the two evaluation sets:

| Metric | Combined v2 (Modifier On, $n=11$) | Combined No-Mod (Modifier Off, $n=11$) | Paired Delta |
|---|---|---|---|
| **Route Accuracy** | **0.8182 (9/11)** | 0.6364 (7/11) | **-0.1818 (-22.2% relative)** |
| **Context Relevance** | **0.9167** | 0.5000 | **-0.4167 (-45.5% relative)** |
| **Groundedness** | **1.0000** | **1.0000** | 0.0000 |
| **Faithfulness** | 0.8701 | **0.9004** | +0.0303 |
| **Hallucination Rate** | **0.0000** | **0.0000** | 0.0000 |
| **Mean Latency** | 188.6 s | **131.2 s** | **-57.4 s (-30.4%)** |

Across both slices, **disabling the modifier step causes Context Relevance to collapse from 0.9167 to 0.5000 (-45.5%), driving an 18.2 percentage-point drop in final Route Accuracy**.


---

## 3. Qualitative Breakdown & Failure Modes

### S20: Narrow Plot (5.5 m Width) - Road-Width Height Interaction
- **Scenario:** Single dwelling on a narrow $5.5\text{ m} \times 15.0\text{ m}$ plot abutting an $8.0\text{ m}$ road. Under Table 8, plots $\le 6.0\text{ m}$ wide permit zero side setback on one side. However, because the road is $< 9.0\text{ m}$, the height cap under `ZR2015:T10:ii.b` ($11.5\text{ m}$) must be verified as a mandatory topic.
- **With Modifier (`real_v2`):**
  - Primary search retrieved Table 8 for setbacks.
  - The modifier step inspected the proposal's $8.0\text{ m}$ road and derived a query for road-width height restrictions.
  - Retrieved `ZR2015:T10:ii.b` (Context Relevance = **1.0000**).
  - Assessor verified both setbacks and height compliance, routing cleanly to **`clear-for-submission`**.
- **Without Modifier (`real_nomod`):**
  - The agent stopped after retrieving Table 8.
  - Missed `ZR2015:T10:ii.b` completely (`gold_missing: ['ZR2015:T10:ii.b']`, Context Relevance = **0.5000**).
  - The deterministic router (`src/bpc/agents/router.py`) checked mandatory topic coverage and discovered no verified finding for `height`.
  - Result: Failed route to **`specialist-review`** with reason: `Insufficient verified evidence to route automatically: no verified finding for: height`.

### S16: Residential (Mixed) 1200 sq.m with Coverage Violation
- **Scenario:** Mixed residential proposal on a $15.0\text{ m}$ road with proposed ground coverage of 68% against a 65% ceiling.
- **With Modifier:** 7 distinct provisions recorded and cross-referenced. Both coverage and road-width setback rules were verified. Routed to `revise-and-recheck` with full violation citation.
- **Without Modifier:** The primary coverage limit was flagged, but the secondary road-width setback modifier was omitted from the findings dossier.

---

## 4. Architectural Analysis: The Section 4.1 Reference Case (S01)

The reference proposal (S01, documented in `docs/reference_case.md`) illustrates why linear RAG fails on municipal zoning codes:

$$\text{Proposal: } 108\text{ m}^2 \text{ plot, } 6.0\text{ m road, Height } = 12.5\text{ m (Stilt + GF + 3)}, \text{ Setbacks } = 1.5/1.0/1.0/1.0\text{ m}$$

1. **Table 8 (Setbacks):** For buildings $\le 11.5\text{ m}$, Table 8 requires 1.0 m side setbacks and 1.44 m front setback. The proposal appears compliant.
2. **Table 10 Row 1 (FAR & Coverage):** Permissible FAR is 1.75; proposed is 1.70. Permissible coverage is 75%; proposed is 60%. The proposal appears compliant.
3. **The Hidden Modifier (`ZR2015:T10:ii.b`):** Note (ii)(b) under Table 10 specifies that for roads $< 9.0\text{ m}$, maximum permissible height is capped at **$11.5\text{ m}$ or Stilt+GF+2**, irrespective of FAR.
4. **The Cascade:** Because height ($12.5\text{ m}$) exceeds $11.5\text{ m}$, Section 3.1(iii) mandates switching from Table 8 to Table 9 (requiring $5.0\text{ m}$ setbacks all round).

### Retrieval Ranking Comparison (Measured on 881-chunk Corpus)

| Query Phrasing | Search Mode | `ZR2015:T10:ii.b` in Top 6 Results |
|---|---|---|
| *"setbacks for residential building on 9x12m plot"* | Hybrid (Dense + BM25) | **No** (Rank > 15) |
| *"Residential building proposed on a small plot abutting a narrow road"* | Hybrid (Dense + BM25) | **No** (Rank > 20) |
| *"maximum height of building restricted by road width"* (Modifier Query) | Hybrid (Dense + BM25) | **Rank 1** |

A single-pass retrieval architecture relies on semantic similarity between the user's input proposal and the legal text. Because the user's proposal does not state "my height might violate a road width rule", standard vector similarity will never bridge the gap to Table 10 Note (ii)(b). Only an **agentic loop with deliberate variable inspection** generates the bridge query.

---

## 5. Engineering Trade-off & Operational Conclusions

| Dimension | Modifier Enabled (`real_v2`, $n=11$ paired) | Modifier Disabled (`real_nomod`, $n=11$ paired) | Decision Guidance |
|---|---|---|---|
| **Decision Quality** | High (81.8% route accuracy, 91.7% context relevance) | Medium-Low (63.6% route accuracy, 50.0% context relevance) *(raw aggregate: 64.3% acc, 42.9% ctx)* | Safety-critical applications must enable modifiers |
| **Latency Profile** | 188.6 s mean per scenario | 131.2 s mean per scenario (-30.4%) *(raw aggregate: ~149 s)* | High-throughput interactive tiers may use no-mod for initial screening |
| **API Cost** | +1 tool call / +2.5k tokens per run | Baseline | Modest token increase justified by legal correctness |
| **Failure Mode** | Provider quota bound (requires retries & backoff) | False clearances or unnecessary specialist escalations | Safe fail-open via router escalation preserved in both |

### Key Takeaway for AgentOps
In complex regulatory domains, **agents must not merely answer questions; they must actively interrogate their own incomplete knowledge**. The modifier step is a demonstrable example of how deterministic reflection transforms an unreliable RAG search into a legally sound compliance checker.
