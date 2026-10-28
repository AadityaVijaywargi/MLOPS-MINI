# Modifier-Step Comparison: Real v2 (Modifier Enabled) vs Real No-Mod (Modifier Disabled)

- **Author / Teammate:** Friend 3 (Aarav Yuval B G, SRN: PES1UG24AM004)
- **Evaluation Set:** Slice 3 (Scenarios S16–S22) and Cross-Slice Aggregation (Slices 2 & 3)
- **Model:** Hosted free-tier LLM via OpenAI-compatible gateway (configured via `LLM_PRIMARY_MODEL` at `LLM_PRIMARY_BASE_URL`)
- **Target Variable:** Research agent modifier pass (`MODIFIER_SEARCH_ENABLED=true` vs `MODIFIER_SEARCH_ENABLED=false`)
- **Artifacts Compared:** `eval/results/real_v2_part3.json` vs `eval/results/real_nomod_part3.json`

---

## 1. Execution Overview & Provider Degradation Audit

The modifier step is an agentic reflection pass executed at the conclusion of primary research. It inspects all provisions recorded so far, identifies dependent variables that can be modified or capped by another bye-law (such as road width restricting building height or plot size overriding setbacks), and issues derived cross-reference queries back to the retrieval loop.

When the modifier step is disabled (`MODIFIER_SEARCH_ENABLED=false`), secondary overriding provisions located outside the primary zone tables are omitted from retrieval.

### Per-Scenario Run Status in Slice 3:
- **`real_v1_part3`:** 2 scored (`S17`, `S22`), **5 provider degraded** (`S16`, `S18`, `S19`, `S20`, `S21`) due to upstream Gemini free-tier rate/quota limits.
- **`real_v2_part3`:** 4 scored (`S16`, `S19`, `S20`, `S22`), **3 provider degraded** (`S17`, `S18`, `S21`).
- **`real_nomod_part3`:** **All 7 scored** (`S16` through `S22`), 0 provider degraded.

Per the project evaluation protocol, provider-degraded runs reflect upstream infrastructure throttling rather than system reasoning quality and are excluded from metric scoring. Consequently, comparing raw aggregate rows directly between files with different scored scenario sets introduces sampling asymmetry. Below, we present both the raw file summaries and the strictly paired, comparable comparison.

---

## 2. Strictly Paired Comparison on Common Scenarios (S16, S19, S20, S22)

To ensure a rigorous, apples-to-apples comparison, this table evaluates **only the scenarios successfully scored in both Slice 3 runs** ($n = 4$):

| Metric | Real v2 (Modifier On, $n=4$) | Real No-Mod (Modifier Off, $n=4$) | Delta (Paired) | Relative Impact |
|---|---|---|---|---|
| **Route Accuracy** | **0.7500 (3/4)** | 0.5000 (2/4) | **-0.2500** | **-33.3% relative drop** (-25.0 percentage points) |
| **Context Relevance** | **0.8750** | 0.7500 | **-0.1250** | **-12.5 percentage points** (gold clauses missed) |
| **Groundedness** | **1.0000** | **1.0000** | 0.0000 | Perfect verbatim quoting maintained |
| **Faithfulness** | 0.9643 | **1.0000** | +0.0357 | Arithmetic valid on retrieved subset |
| **Hallucination Rate** | **0.0000** | **0.0000** | 0.0000 | Zero hallucinated citations |
| **Violation Recall** | 0.6667 | 0.6667 | 0.0000 | Violations recalled identically on $n=4$ |
| **Mean Latency** | 412.4 s | **279.7 s** | **-132.7 s** | **32.2% speedup** without reflection turn |
| **Mean LLM Calls** | 20.5 calls | 21.0 calls | +0.5 calls | Comparable model call count |

*(Reference Raw Aggregates: `real_v2_part3` raw scored $n=4$ route accuracy = 0.7500; `real_nomod_part3` raw scored $n=7$ route accuracy = 0.5714).*

---

## 3. Cross-Slice Aggregation (Slices 2 & 3 Strictly Paired, $n=11$)

In Slice 2 (S09–S15, Friend 2), all 7 scenarios completed without provider degradation in both arms. Combining those 7 scenarios with the 4 non-degraded Slice 3 scenarios yields **11 strictly comparable, paired scenarios** across the two evaluation sets:

| Metric | Real v2 (Modifier On, $n=11$) | Real No-Mod (Modifier Off, $n=11$) | Paired Delta |
|---|---|---|---|
| **Route Accuracy** | **0.8182 (9/11)** | 0.6364 (7/11) | **-0.1818 (-22.2% relative)** |
| **Context Relevance** | **0.9167** | 0.5000 | **-0.4167 (-45.5% relative)** |
| **Groundedness** | **1.0000** | **1.0000** | 0.0000 |
| **Faithfulness** | 0.8701 | **0.9004** | +0.0303 |
| **Hallucination Rate** | **0.0000** | **0.0000** | 0.0000 |
| **Mean Latency** | 188.6 s | **131.2 s** | **-57.4 s (-30.4%)** |

Across both slices, **disabling the modifier step causes Context Relevance to collapse from 0.9167 to 0.5000 (-45.5%), driving an 18.2 percentage-point drop in final Route Accuracy**.

---

## 4. Key Scenario Breakdown & Mechanism Analysis

### S20: Narrow Plot (5.5 m Width) on 8 m Road
- **Ground Truth Requirement:** Narrow plot ($< 6.0\text{ m}$) under Table 8 allows zero side setback on one side. Mandatory topic check requires height provision under road-width constraints (`ZR2015:T10:ii.b`).
- **Real v2 (Modifier On):**
  - Modifier step inspected recorded provisions, identified the narrow road ($8.0\text{ m} < 9.0\text{ m}$), and derived the height-by-road-width query.
  - Retrieved `ZR2015:T10:ii.b` (Context Relevance = **1.0000**).
  - Assessor verified compliance across all mandatory topics, routing cleanly to **`clear-for-submission` (Correct)**.
- **Real No-Mod (Modifier Off):**
  - Stopped after retrieving Table 8 for setbacks.
  - Missed `ZR2015:T10:ii.b` completely (`gold_missing: ['ZR2015:T10:ii.b']`, Context Relevance = **0.5000**).
  - The deterministic router (`src/bpc/agents/router.py`) checked mandatory topic coverage and discovered no verified finding for `height`.
  - Result: Failed route to **`specialist-review` (Incorrect)** with reason: `"Insufficient verified evidence to route automatically: no verified finding for: height"`.

### S16: Residential (Mixed) on 15 m Road with Coverage Violation
- **Ground Truth Requirement:** RMP-2015 Table 11/12 coverage limit (65%). Proposed is 68%.
- **Real v2:** Evaluated 7 distinct provisions including road-width context; flagged coverage violation and routed to `revise-and-recheck` with **1.0000** violation recall.
- **Real No-Mod:** Evaluated 6 provisions; flagged primary coverage limit, but missed cross-referenced road-width setback modifier.

---

## 5. Deep Dive: Section 4.1 Reference Case (S01) and Table 10 Note (ii)(b)

The benchmark reference proposal (S01, `eval/examples/reference_case.json`) demonstrates the core architectural necessity of the modifier step:

1. **The Trap:**
   - Single-family dwelling on a $9.0\text{ m} \times 12.0\text{ m} = 108\text{ m}^2$ plot on a $6.0\text{ m}$ road.
   - Proposed height: $12.5\text{ m}$ (Stilt + GF + 3). Setbacks: Front $1.5\text{ m}$, Rear $1.0\text{ m}$, Sides $1.0\text{ m}$.
   - Looking purely at the primary setback table (Table 8) and FAR table (Table 10 row 1), setbacks and FAR appear satisfied.
2. **The Hidden Constraint:**
   - Under Table 10 (FAR), **Note (ii)(b)** (`ZR2015:T10:ii.b`) states:
     > *"If the road width is less than 9.0 m, then the maximum height is restricted to 11.5 meters or Stilt +GF+2 floors (whichever is less) irrespective of the FAR permissible."*
   - Exceeding 11.5 m also moves the building under §3.1(iii) into Table 9 ($5.0\text{ m}$ setbacks all round).
3. **Retrieval Failure without Modifier:**
   - Standard dense and BM25 searches for `"setbacks for residential building on 9x12m plot"` rank Table 8 and Table 10, but **rank `ZR2015:T10:ii.b` outside the top 6**.
   - Because the proposal never mentions "height restriction by road width", a single-pass RAG search never queries for it.
4. **Agentic Modifier Resolution:**
   - The modifier step inspects the proposal's $6.0\text{ m}$ road and generates the derived query: `"maximum height of building restricted by road width"`.
   - On the hybrid FAISS+BM25 index, this query ranks `ZR2015:T10:ii.b` **Rank 1**.
   - With modifier enabled, S01 catches both the height violation ($12.5\text{ m} > 11.5\text{ m}$) and the cascading Table 9 setback violation, routing correctly to `revise-and-recheck`. Without it, the violation is missed.

---

## 6. Engineering Conclusion & Trade-off Assessment

The modifier step embodies the transition from a passive RAG pipeline to an active multi-agent system:
- **Cost / Latency:** It adds 1 tool turn and approximately 40–130 seconds per run on complex proposals.
- **Accuracy / Safety:** It prevents false clearances and legal omissions, lifting multi-slice Context Relevance from 0.5000 to 0.9167 and Route Accuracy from 0.6364 to 0.8182 on comparable scenarios.
- **Verdict:** For legal, regulatory, and municipal compliance systems where requirements interact non-locally, the modifier reflection step is strictly necessary.
