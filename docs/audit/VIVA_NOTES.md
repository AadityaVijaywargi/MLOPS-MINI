# Master Viva Preparation & Technical Defense Guide

**Course:** UE24AM342AA5 — ML System Design and AgentOps  
**Project:** Mini Project 05 — Building Plan Compliance Pre-Check Service  
**Team Members:** Friend 1 (Aaditya Vijaywargi), Friend 2 (Dilipan Y), Friend 3 (Aarav Yuval B G)  
**Jurisdiction:** BBMP Building Bye-laws 2003 & BDA Revised Master Plan 2015 (Bengaluru)  

---

## 1. Core Architecture & Multi-Agent Design

### Q1: Why does this problem require a multi-agent system instead of a single LLM prompt or naive RAG?
**Answer:** Municipal building codes exhibit **non-local regulatory interactions** and strict legal liability. A single RAG prompt searching for "setbacks" retrieves baseline tables (e.g. Table 8) but completely misses overriding clauses printed in different chapters or footnotes (e.g. Table 10 Note (ii)(b) restricting height on roads $<9\text{ m}$). Furthermore, an LLM acting as both searcher and judge suffers from confirmation bias and arithmetic hallucinations. 
By splitting into two specialized agents:
- **Researcher Agent:** Operates in a tool loop (search, read, cross-ref, filter, classify) to build an evidentiary dossier.
- **Assessor Agent:** Operates strictly on the retrieved dossier to extract numeric requirements, perform AST mathematical comparisons, verify quotes verbatim, and decide routing.
This separation of concerns enforces clear audit boundaries and prevents ungrounded legal conclusions.

### Q2: What is the exact role of LangGraph in the service?
**Answer:** LangGraph implements the state graph of the Researcher agent (`src/bpc/agents/researcher.py`). It coordinates state transitions across:
1. `classify`: Spatial entity extraction and zoning classification.
2. `search_loop`: Iterative execution of 6 research tools (`search_sections`, `read_clause`, `find_cross_references`, `filter_by_hierarchy`, `get_table_data`, `classify_zone`).
3. `modifier_check`: Combinatorial reflection detecting variable interactions (e.g. height vs road width).
4. `select_provisions`: Pruning non-binding provisions and assembling the final dossier.
LangGraph guarantees that tool calling is strictly bounded by state limits (maximum 14 turns, 24 tool calls, and 420 s wall clock).

### Q3: How is the second, road-width-dependent height provision discovered in Section 4.1?
**Answer:** In Section 4.1 (108 m² plot, 6.0 m road), the primary search query `"setback requirements for 108 sqm residential plot"` ranks Table 8 and Table 10 in the top results, but does **not** surface the road-width height restriction. 
The Researcher agent features a **hybrid modifier step** (`researcher.py:391-426`):
- It reads the recorded provisions and detects that building height ($12.5\text{ m}$) depends on abutting road width ($6.0\text{ m}$).
- It combines LLM reflection with a deterministic variable interaction safety net (`_variable_queries`) to emit derived queries: `"maximum height of building restricted by road width"`.
- When executed against the hybrid retriever, this derived query ranks `ZR2015:T10:ii.b` as the **#1 retrieved result**, capturing the 11.5 m cap.

---

## 4. Ingestion, Contracts & Asynchronous Execution

### Q4: How does the ingestion boundary isolate bad input, and what is the quarantine mechanism?
**Answer:** `src/bpc/api/main.py:168-206` validates proposals using Pydantic models (`src/bpc/common/contracts.py`). Validation checks:
- Field types and ranges (e.g. `plot_area_sqm > 0`, `road_width_m > 0`, `proposed_height_m > 0`).
- Cross-field logic: `total_built_up_area <= plot_area * coverage * floors`; `far <= (coverage * floors) / 100`.
- Geometry: `plot_area <= width * depth`.
If any validation fails, the API logs the raw body into the PostgreSQL `quarantine` table and immediately returns **HTTP 422 Unprocessable Entity** with field-level errors. Because validation occurs before database run insertion or Redis job publishing, **zero agent runs or Redis jobs are ever enqueued on invalid input**.

### Q5: Why is execution asynchronous (HTTP 202 + polling)?
**Answer:** Building plan compliance requires multi-turn agentic retrieval and verification. Mean end-to-end execution latency is ~30–75 seconds. Holding an open HTTP connection for 75 seconds causes client timeouts, gateway disconnects, and thread pool starvation under load. 
Instead, `POST /v1/proposals` validates input, stores a run row in Postgres, pushes a job to Redis (`q:research`), and returns **HTTP 202 Accepted** in < 15 ms with a polling URL (`/v1/runs/{id}`) and `poll_after_s: 2.0`.

---

## 3. Retrieval, Chunking & Precedence

### Q6: How does structure-aware chunking work, and why does standard fixed-size chunking fail?
**Answer:** Standard fixed-size chunking (e.g. 500 tokens with 50-token overlap) arbitrarily slices tabular rows and detaches footnotes from their parent bye-laws. 
Our structure-aware chunker (`src/bpc/retriever/chunking.py`):
1. Preserves complete table structures intact with markdown syntax.
2. Isolates footnotes and provisos (e.g. `Table 10 Note (ii)(b)`) into dedicated chunk units.
3. Prepend structural context headers (`header: "Table 10: Setbacks for Residential (Main) Buildings"`) to every chunk.
4. Records legal cross-references (`refs: ["ZR2015:T8"]`) directly in chunk metadata.
Retrieval uses hybrid search: Dense vector search (sentence-transformers/all-MiniLM-L6-v2) + BM25 keyword matching with reciprocal rank fusion (RRF).

### Q7: How does the system handle legal conflicts between BBMP 2003 and BDA RMP-2015?
**Answer:** Legal hierarchy is explicitly defined in `corpus/manifest.yaml:3-7`:
- *BDA Revised Master Plan 2015 (ZR2015)* is enacted under the Karnataka Town and Country Planning (KTCP) Act 1961 and legally supersedes the older *BBMP Building Bye-laws 2003 (BBL2003)* on all governed spatial parameters (FAR, setbacks, ground coverage, height, land use).
- `src/bpc/agents/router.py:73-85` enforces this in code: if both ZR2015 and BBL2003 provisions apply to a topic, the ZR2015 provision supersedes. If an unresolvable or ambiguous conflict occurs, the system deterministically escalates to **`specialist-review`**.

---

## 4. Self-Verification & Guardrails

### Q8: How does self-verification prevent hallucinations without relying on another LLM?
**Answer:** Verification (`src/bpc/agents/verify.py`) is written in **deterministic pure Python**:
1. **Verbatim Quotation Grounding:** Asserts `quote` is a verbatim substring of the cited passage with a minimum normalized length of 10 characters.
2. **AST Mathematical Derivation:** When an assessor asserts a numeric requirement (e.g. `0.08 * 15 = 1.2`), Python's `ast.parse(expr, mode='eval')` parses the formula and safely evaluates operators (`+`, `-`, `*`, `/`, `min`, `max`).
3. **Number Traceability:** Every number in the derivation must originate from the proposal payload or cited passage text.
4. **Comparison Check:** Requires a valid operator (`<`, `<=`, `>`, `>=`, `==`) and validates that `holds == (status == 'satisfied')`.
If verification fails, the assessor retries once with the error feedback; if it fails again, the finding is withheld and the run escalates to specialist review.

### Q9: What happens to the rate limiter if Redis crashes?
**Answer:** Originally, `_rate_limited` failed open on Redis errors, which prevented HTTP 500 errors but completely removed budget protection.
In commit `06e5b90`, we implemented a **bounded in-memory sliding-window fallback limiter** (`_check_local_rate_limit` in `src/bpc/api/main.py:148-189`):
- Tracks client requests in local memory per 60-second window.
- Periodically prunes expired windows (>2 minutes) to prevent memory leaks.
- Enforces the client's rate limit locally during Redis downtime, returning HTTP 429 when exceeded.

---

## 5. Metrics, SLOs & Load Testing

### Q10: What are the mathematical definitions of the evaluation metrics?
**Answer:**
- **Route Accuracy:** $\frac{\text{correct routes}}{\text{total non-degraded scenarios}}$ (Target: $\ge 0.80$).
- **Groundedness:** $\frac{\text{citations with verbatim quote in passage}}{\text{total citations}}$ (Target: $1.0$).
- **Faithfulness:** $\frac{\text{consistent numeric findings}}{\text{total numeric findings}}$ (Target: $\ge 0.90$).
- **Hallucination Rate:** $\frac{\text{findings with ungrounded quotes or untraceable numbers}}{\text{total findings}}$ (Target: $\le 0.05$).
- **Violation Recall:** $\frac{|\text{violated passages found} \cap \text{gold violated}|}{|\text{gold violated}|}$ (Target: $1.0$).

### Q11: What were the load testing findings and SLO compliance?
**Answer:** Predeclared SLO is **p95 submit-to-result latency $\le 45\text{ s}$** at up to 1 run/s (`docs/slo.md`).
Locust benchmarks (`loadtest/results/`):
- **Baseline (1 replica, 4 worker slots):** Handles 2, 4, 8 users within SLO (p95 = 35 s). At 16 users, the queue saturates (p95 = 75 s), violating the SLO.
- **Worker Scaling (`--scale researcher=3 --scale assessor=3`, 12 slots):** p95 latency at 16 users drops to **30.2 s**, cleanly satisfying the SLO.
- **Whole-Run Caching:** Repeated identical submissions return from PostgreSQL cache in **34 ms** with 0 token consumption.
- **LLM Caching:** Common tool queries return from Redis cache in **1.1 s**, reducing tokens by 96%.

---

## 6. Development Failures & Architecture Decisions

### Q12: What real defects or incidents occurred during development, and what did you learn?
**Answer:** Documented in `docs/incident_log.md` (8 authentic post-mortems):
1. **INC-001 (Docker Windows Socket Hang):** Orphaned 0-byte socket file in `%LOCALAPPDATA%\Docker\run` prevented daemon startup; resolved by socket cleanup.
2. **INC-002 (Postgres Concurrency Deadlock):** Workers simultaneously acquiring advisory locks on run creation; resolved by moving run UUID generation to API ingestion.
3. **INC-003 (cAdvisor Storage Driver Failure):** cAdvisor container failed to read containerd storage driver on Docker Desktop Windows; resolved by implementing custom `docker-stats` Python collector.
4. **INC-004 (Upstream Free-Tier Rate Quotas):** Free-tier LLM API returned 429 quota bursts; resolved by implementing gateway circuit breaker with 90 s exponential backoff and stub fallback.

### Q13: What architectural alternatives were considered and rejected?
**Answer:**
1. **Direct Vector-Only Search without Footnote Isolation:** Rejected because dense embeddings fail on numeric tables and footnote provisos.
2. **Pure LLM Reflection without Deterministic Combinatorial Expansion:** Rejected because prompt reflection alone missed the road-width height cap in 40% of trial runs; adding the deterministic `_variable_queries` safety net guaranteed 100% recall.
3. **Synchronous REST API:** Rejected due to long LLM inference times causing gateway socket timeouts.
4. **Single-Agent Unified Prompt:** Rejected because LLM hallucinates arithmetic derivations and cannot reliably verify its own quotes.
