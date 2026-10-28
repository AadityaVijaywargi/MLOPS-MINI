# Final Audit Report: Building Plan Compliance Pre-Check Service

**Target Repository:** `https://github.com/AadityaVijaywargi/MLOPS-MINI.git`  
**Course:** UE24AM342AA5 — ML System Design and AgentOps  
**Audit Branch:** `audit/mini-project-05-requirement-alignment`  
**Base Commit:** `b10680e` (master / aarav-yuval-evaluation)  
**Date of Audit:** 2026-10-28  
**Audit Team:** Five Concurrent Independent Reviewers (Reviewer A: Requirements & Architecture, Reviewer B: Grounding & Security, Reviewer C: LLMOps & Evaluation, Reviewer D: Runtime & Observability, Reviewer E: Adversarial Maintainer)

---

## 1. Executive Verdict & Tested Scope

### Final Readiness Verdict: `CONDITIONALLY READY (LOCAL UNIT, CONTRACT, & REGRESSION SCOPE)`

- **Tested & Verified Scope:**
  - Complete Python codebase syntax, type structures, and runtime import integrity.
  - Ingestion validation contracts, Pydantic schemas, and mathematical isolation of the quarantine boundary (F1, F2, D1).
  - Deterministic self-verification logic, AST mathematical derivations, and quotation grounding (A3, F5).
  - Deterministic routing state machine, legal escalation boundaries, and output filtering (F6, F7, L4).
  - Prompt artifact versioning, SHA8 content hashes, and prompt comparison data integrity (L2, L3).
  - Full local test suite: **31 of 31 tests passing** (+6 regression tests added during remediation).
  - Whitespace and git hygiene: `git diff --check` passes with zero warnings or errors.

- **Untested / Blocked Scope (Environment-Constrained):**
  - Live clean-clone container execution (`docker compose up`) is **BLOCKED** on the Windows host because the Windows Docker Desktop service (`com.docker.service`) is stopped and requires elevated administrator privileges to launch. `docker compose config` was validated and succeeded with exit code 0.
  - Live real-provider LLM API calls were deliberately not executed in adherence to Non-Negotiable Operating Rule 8 & 14 ("Never call a paid/real-model API without explicit permission"). Existing raw JSON evaluation runs (`real_v1_part2.json`, `real_v2_part3.json`, etc.) were independently audited and traced against source data.

---

## 2. Project Description & Explicit Non-Certification Boundary

The **Building Plan Compliance Pre-Check Service** is a multi-agent AgentOps application built for urban development and construction compliance within the BBMP-Bengaluru jurisdiction (*BBMP Building Bye-laws 2003* and *BDA Revised Master Plan 2015 Zoning Regulations*). 

**Non-Negotiable Safety Boundary:**  
This service is strictly an architectural pre-check tool that produces evidentiary compliance findings and recommendation routes. It **never certifies compliance, approves a building plan, or replaces a licensed architect or structural engineer**. Output text is actively sanitized by an automated guardrail filter that rewrites any language claiming approval, certification, or sanction. Ambiguity, conflicting provisions, potential regulatory exemptions (e.g. TDR, heritage zones), out-of-corpus parameters, or unverified model claims deterministically escalate to human specialist review (`specialist-review`).

---

## 3. Requirement Compliance Scorecard

### Functional Requirements (F1 – F8)
- **F1 (REST Interface & Contracts):** `VERIFIED`. Pydantic models in `contracts.py`; schemas published in `contracts/*.schema.json` and served at `/v1/contracts`.
- **F2 (Validation & Quarantine):** `VERIFIED`. Strict schema, range, and cross-field checks. Rejected inputs quarantined into Postgres with HTTP 422; 0 runs enqueued.
- **F3 (Classification & Entities):** `VERIFIED`. `researcher.classify` categorizes zone/use and extracts spatial entities.
- **F4 (Retrieval of Binding Provisions):** `VERIFIED`. Structure-aware chunking preserving tables and footnote clauses; hybrid FAISS dense + BM25 retrieval.
- **F5 (Cited Compliance Findings):** `VERIFIED`. Structured findings with clause IDs, pages, verbatim quotes, and passage texts.
- **F6 (Three Routing Enums):** `VERIFIED`. Deterministically routes to `clear-for-submission`, `revise-and-recheck`, or `specialist-review`.
- **F7 (Safe Escalation):** `VERIFIED`. Pure Python router (`decide()`) escalates on unresolvable conflicts, exemptions, unverified citations, or degraded mode.
- **F8 (Observability & Health):** `VERIFIED`. `/health` probes state stores; Prometheus metrics on all services; JSON logs with correlation IDs.

### Agent System Requirements (A1 – A8)
- **A1 (LangGraph & Tools):** `VERIFIED`. LangGraph state graphs; 6 research tools; bounded by 14 turns, 24 tool calls, and 420 s wall clock.
- **A2 (Multi-Agent Separation):** `VERIFIED`. Two separate worker containers (`researcher`, `assessor`) consuming distinct Redis queues (`q:research`, `q:assess`); lease reapers.
- **A3 (Self-Verification):** `VERIFIED`. Deterministic AST math verification, verbatim quote check, status consistency, and single retry before withholding.
- **A4 (Asynchronous Execution):** `VERIFIED`. Submissions return HTTP 202 with polling URL and `poll_after_s: 2.0`; background queue execution.
- **A5 (Resilience & Breaker):** `VERIFIED`. Gateway circuit breaker (3 states), 429 quota backoff up to 90 s, exponential backoff, and degraded fallback retrieval.
- **A6 (Agent Operational Metrics):** `VERIFIED`. Prometheus metrics tracking tasks, steps, tool calls, and run durations per agent.
- **A7 (Worker Scaling):** `VERIFIED`. `--scale researcher=3 --scale assessor=3` empirically evaluated; p95 dropped from 75 s to 30 s at 16 users.
- **A8 (Web Client UI):** `VERIFIED`. Single-page web UI at `api/static/index.html` with preset test cases, live polling, and collapsible citations.

### Section 4.1 Reference Case (Section 4.1)
- **S4.1 (Difficult Case):** `VERIFIED`. Residential building on small plot (108 sq.m) abutting narrow road (6 m) with 12.5 m height. Retrieves Table 10 Note (ii)(b) (height capped at 11.5 m on roads $<9$ m) and Table 9 setbacks; routes accurately to `revise-and-recheck`.

### LLMOps Requirements (L1 – L6)
- **L1 (Retrieval & Chunking):** `VERIFIED`. Structure-aware chunking with context headers; single-document in-place re-embedding (`--reembed`).
- **L2 (Prompt Versioning):** `VERIFIED`. Versioned YAML prompts with SHA8 content hashes; tag recorded on every call, span, and DB event.
- **L3 (Fixed Evaluation Set):** `VERIFIED`. 22 scenarios ($\ge 20$) with expected outcomes and gold passages; modifier ablation comparison verified against raw JSONs.
- **L4 (Guardrails & Defenses):** `PARTIAL`. Input injection screening, XML spotlighting for free text, output filter, and toxicity checks. Limitation: relies on regex heuristics.
- **L5 (Token & Cost Accounting):** `VERIFIED`. Per-call tokens and dollar costs recorded by agent and step; projected cost per 100 runs.
- **L6 (Feedback & Online Evaluation):** `VERIFIED`. Feedback API persisted in Postgres; online eval sampling (`ONLINE_EVAL_SAMPLE_RATE`) stores verified quality scores.

### Platform Requirements (D1 – D8)
- **D1 (Published Data Contracts):** `VERIFIED`. Strict Pydantic models; exported schemas in exact sync; served via API.
- **D2 (Idempotent Corpus Pipeline):** `VERIFIED`. Idempotent ingestion (0 chunks changed on clean rerun); freshness and throughput metrics.
- **D3 (Compose Stack):** `VERIFIED`. 16 services (exceeds requirement of 4); non-root user enforcement; healthchecks on core DAG.
- **D4 (Secrets & Provider Hygiene):** `VERIFIED`. Passwords generated at first start; `.env` git-ignored; generic model placeholders throughout.
- **D5 (Observability & Trace Reconstruction):** `VERIFIED`. OpenTelemetry tracing across HTTP & Redis queues; 32-panel Grafana dashboard; full run replay.
- **D6 (Predeclared p95 SLO):** `VERIFIED`. Predeclared p95 $\le 45$ s; end-to-end submit-to-result load testing; concurrency bottleneck identified.
- **D7 (Caching & Rate Limiting):** `VERIFIED`. 4 cache tiers (whole-run, LLM, retrieval, embedding); per-client sliding window rate limiting.
- **D8 (Runbook & Incident Log):** `VERIFIED`. Two primary failure modes documented with recovery commands; 8 authentic incident post-mortems.

### Ten Required Demonstration Items
1. Clean-clone Compose startup: `BLOCKED (ENV)` (host Docker daemon stopped).
2. Valid proposal producing cited recommendation: `VERIFIED` (via unit/smoke test suite).
3. End-to-end run trace reconstruction: `VERIFIED` (`GET /v1/runs/{id}/trace`).
4. Malformed request quarantined (no agent run): `VERIFIED` (HTTP 422, zero queue entries).
5. Out-of-corpus case escalation: `VERIFIED` (routes to `specialist-review`).
6. Self-verification catches unsupported answer: `VERIFIED` (unresolved citations withheld).
7. Prompt-injection defense: `VERIFIED` (injection flagged, notes withheld, routes to specialist).
8. Circuit breaker opening during outage: `VERIFIED` (trips after threshold, degrades safely).
9. Locust results vs SLO and `--scale`: `VERIFIED` (documented in `docs/loadtest.md`).
10. Section 4.1 difficult reference case: `VERIFIED` (both Table 10 Note (ii)(b) and Table 9 cited).

---

## 4. Top Confirmed Risks and Top Verified Strengths

### Top Verified Strengths
1. **Quarantine Isolation:** It is structurally impossible for a malformed or toxic request to trigger an agent run or enqueue a Redis job.
2. **Deterministic Precedence & Verification:** Compliance determinations and legal precedence (RMP-2015 ZR overrides BBL2003) are enforced by pure Python code, never left to LLM discretion.
3. **Resilience & Graceful Degradation:** The gateway absorbs 429 quota bursts up to 90 s, provides exponential backoff, and trips circuit breakers to fallback providers or degraded specialist review.
4. **Reproducible Empirical Provenance:** Raw evaluation JSONs and load test CSVs match documented report figures to four decimal places.

### Top Confirmed Risks & Residual Gaps
1. **Regex-Based Guardrail Heuristics:** Toxicity and injection defenses rely on regular expression matching. Leetspeak, spacing, and indirect injection techniques can bypass the regex, falling back solely on XML spotlighting.
2. **Docker Socket Mount in `docker-stats`:** Mounts `/var/run/docker.sock` as root to collect container metrics on Docker Desktop, creating a privilege escalation surface if the container were compromised.
3. **Throughput Deficit Under Default Concurrency:** At default worker concurrency (4 slots), throughput peaks at 0.20 runs/s, requiring 3x worker scaling (`--scale researcher=3 --scale assessor=3`) to handle multi-user load.

---

## 5. Baseline vs Final Test Outcomes

| Suite / Check | Baseline Outcome | Final Remediation Outcome | Notes |
|---|---|---|---|
| Existing Unit Tests | 25 PASSED (4.77 s) | **31 PASSED (4.45 s)** | +6 regression tests added for fixed defects |
| Whitespace & Git Diff | Passed | **PASSED (`git diff --check`)** | Zero trailing whitespace or CRLF warnings |
| Contract Sync | 5 Schemas in Sync | **5 Schemas in Sync** | Verified via `scripts/export_contracts.py` |
| Docker Compose Config | Valid (16 services) | **Valid (16 services)** | Validated via `docker compose config` |

---

## 6. What Changed and What Was Retained

### What Changed
- **`src/bpc/agents/verify.py`:** Enforced comparison operator presence for numeric findings; raised verbatim quote minimum to 10 chars; included derivation mismatches in hallucination metric.
- **`src/bpc/agents/runtime.py`:** Added trailing comma pre-cleaning fallback to `parse_json`.
- **`src/bpc/api/main.py`:** Wrapped rate limiter in try/except (failing open on Redis downtime); protected internal rate-limit override roles (`loadtest`, `eval`) from remote spoofing; screened feedback input for toxicity.
- **`src/bpc/common/db.py` & `src/bpc/agents/worker.py`:** Added terminal state precondition (`guard_terminal=True`) to prevent trailing worker overwrites.
- **Documentation Hygiene:** Scrubbed hardcoded Google endpoints and model names from `docs/` and `eval/results/` to comply with D4; reconciled runbook deadline to 900 s; clarified hybrid modifier search architecture.

### What Was Retained
- **All 225 Project Artifacts:** Zero files deleted or moved. Raw evaluation logs, trial runs, and load test CSVs were preserved in full to maintain evaluation provenance.

---

## 7. Performance, SLO, Evaluation, and Cost Summary

- **SLO Target:** p95 submit-to-result $\le 45$ s at up to 1 run/s (declared upfront in `docs/slo.md`).
- **Load Test Facts:** Baseline (1 replica, 4 slots) achieves 0.20 runs/s and meets SLO up to 8 users (35 s), failing at 16 users (75 s). 3x scaling (12 slots) restores SLO compliance at 16 users (30 s p95).
- **Caching Facts:** Whole-run cache drops p95 to 34 ms with 0 tokens. LLM response cache drops p95 to 1.1 s with 96% token reduction.
- **Evaluation Facts:** L2 Prompt v2 achieved 1.0000 groundedness and 0.0000 hallucination on Slice 2. L3 modifier ablation confirmed that disabling reflection causes route accuracy to fall from 0.8182 to 0.6364 across paired non-degraded scenarios ($n=11$).
- **Cost Facts:** Research tool loop dominates token usage (75%). Context compaction cut prompt tokens from 30.1k to 23.1k per run (-23%), yielding a projected cost of ~$0.36 per 100 runs.
