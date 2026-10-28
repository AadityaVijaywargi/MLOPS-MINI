# Final Audit Report: Building Plan Compliance Pre-Check Service

**Target Repository:** `https://github.com/AadityaVijaywargi/MLOPS-MINI.git`  
**Course:** UE24AM342AA5 — ML System Design and AgentOps  
**Audit Branch:** `audit/mini-project-05-requirement-alignment`  
**Base Commit:** `b10680e` (master / aarav-yuval-evaluation)  
**Date of Audit:** 2026-10-28  
**Audit Team:** Five Concurrent Independent Reviewers (Reviewer A: Requirements & Architecture, Reviewer B: Grounding & Security, Reviewer C: LLMOps & Evaluation, Reviewer D: Runtime & Observability, Reviewer E: Adversarial Maintainer), plus Clean-Context Independent Re-Audit.

---

## 1. Executive Verdict & Tested Scope

### Final Readiness Verdict: `CONDITIONALLY READY (LOCAL UNIT, CONTRACT, & REGRESSION SCOPE)`

- **Tested & Verified Scope (Local Execution in this Audit):**
  - Complete Python codebase syntax, type structures, and runtime import integrity.
  - Ingestion validation contracts, Pydantic schemas, and mathematical isolation of the quarantine boundary (F1, F2, D1).
  - Deterministic self-verification logic, AST mathematical derivations, comparison operators, and quotation grounding (A3, F5).
  - Deterministic routing state machine, legal escalation boundaries, and output filtering (F6, F7, L4).
  - Bounded in-memory fallback rate limiter on Redis failure, preserving model budget protection (D7, OPS-004).
  - Safe JSON trailing-comma parser with string literal masking, preventing content mutation (ROB-001, ROB-002).
  - Full local test suite: **35 of 35 tests passing** (+10 regression and robustness tests added across remediation and audit).
  - Whitespace and git hygiene: `git diff --check` passes with zero warnings or errors.

- **Historical Evidence Audited (Checked-in Artifacts Verified Without Live Rerun):**
  - Multi-agent asynchronous execution logs across Slices 1, 2, and 3 (`eval/results/*.json`).
  - L2 prompt comparison (`prompts/assessor.findings.v1.yaml` vs `v2.yaml`) on Slice 2 ($n=7$).
  - L3 modifier reflection ablation (`MODIFIER_SEARCH_ENABLED=true` vs `false`) on Slice 3 ($n=4$ paired, $n=11$ cross-slice).
  - Section 4.1 reference case execution (`real_S01.json`), citing Table 10 Note (ii)(b) and Table 9.
  - End-to-end load testing and worker scaling benchmark results (`loadtest/results/base_1x.md`, `scaled_3x.md`, raw CSVs).

- **Untested / Blocked Scope (Environment-Constrained):**
  - Live clean-clone container execution (`docker compose up`) is **BLOCKED** on the Windows host because the Windows Docker Desktop service (`com.docker.service`) is stopped and requires elevated administrator privileges to launch. `docker compose config` was validated and succeeded with exit code 0.
  - Live real-provider LLM API calls were deliberately not executed in adherence to Non-Negotiable Operating Rule 8 & 14 ("Never call a paid/real-model API without explicit permission").

---

## 2. Project Description & Explicit Non-Certification Boundary

The **Building Plan Compliance Pre-Check Service** is a multi-agent AgentOps application built for urban development and construction compliance within the BBMP-Bengaluru jurisdiction (*BBMP Building Bye-laws 2003* and *BDA Revised Master Plan 2015 Zoning Regulations*). 

**Non-Negotiable Safety Boundary:**  
This service is strictly an architectural pre-check tool that produces evidentiary compliance findings and recommendation routes. It **never certifies compliance, approves a building plan, or replaces a licensed architect or structural engineer**. Output text is actively sanitized by an automated guardrail filter that rewrites any language claiming approval, certification, or sanction. Ambiguity, conflicting provisions, potential regulatory exemptions (e.g. TDR, heritage zones), out-of-corpus parameters, or unverified model claims deterministically escalate to human specialist review (`specialist-review`).

---

## 3. Requirement Compliance Scorecard

Requirements and demonstration items are categorized strictly under the 5-category evaluation taxonomy:
`Unit-tested`, `Historical evidence available`, `Currently integration-tested`, `Blocked by the environment`, and `Not verified or not implemented`.

### Functional Requirements (F1 – F8)
- **F1 (REST Interface & Contracts):** `Unit-tested`. Pydantic models in `contracts.py`; schemas published in `contracts/*.schema.json` and verified in sync via `scripts/export_contracts.py`. Live HTTP serving blocked by Docker daemon.
- **F2 (Validation & Quarantine):** `Unit-tested`. Strict schema, range, and cross-field rejection rules verified in `tests/test_contracts.py`. Rejected inputs return HTTP 422 with field-level errors; code guarantees 0 runs enqueued.
- **F3 (Classification & Entities):** `Historical evidence available`. `researcher.classify` categorizes zone/use and extracts spatial entities. Validated in historical evaluation runs (`real_S01.json`, `real_v1_part2.json`); unit tests cover contract preconditions.
- **F4 (Retrieval of Binding Provisions):** `Unit-tested`. Structure-aware chunking preserving tables and footnote clauses unit-tested in `tests/test_chunking.py`. Live hybrid retriever blocked by Docker daemon.
- **F5 (Cited Compliance Findings):** `Unit-tested`. Structured findings with clause IDs, pages, verbatim quotes, and passage texts unit-tested in `tests/test_verify_router.py`. Live assessor agent run historical in `eval/results/`.
- **F6 (Three Routing Enums):** `Unit-tested`. Deterministically routes to `clear-for-submission`, `revise-and-recheck`, or `specialist-review` (`tests/test_verify_router.py`).
- **F7 (Safe Escalation):** `Unit-tested`. Pure Python router (`decide()`) escalates on unresolvable conflicts, exemptions, unverified citations, or degraded mode (`tests/test_verify_router.py`).
- **F8 (Observability & Health):** `Historical evidence available`. Prometheus metrics instruments and OpenTelemetry tracing implemented in code; live scrape and `/health` probe blocked by Docker daemon.

### Agent System Requirements (A1 – A8)
- **A1 (LangGraph & Tools):** `Unit-tested`. LangGraph state graphs and selection loops unit-tested in `tests/test_researcher_select.py`; bounded by 14 turns, 24 tool calls, and 420 s wall clock; live LLM loop historical.
- **A2 (Multi-Agent Separation):** `Historical evidence available`. Two separate worker containers consuming distinct Redis queues (`q:research`, `q:assess`); lease reapers. Verified historically in `eval/results/real_S01.json`; live container separation blocked by Docker daemon.
- **A3 (Self-Verification):** `Unit-tested`. Deterministic AST math verification, verbatim quote check, status consistency, comparison operators, and single retry before withholding (`tests/test_verify_router.py`).
- **A4 (Asynchronous Execution):** `Historical evidence available`. Submissions return HTTP 202 with polling URL and `poll_after_s: 2.0`; background queue execution. Verified historically in `smoke.py` and Locust benchmarks; live HTTP polling blocked by Docker daemon.
- **A5 (Resilience & Breaker):** `Unit-tested`. Gateway circuit breaker (3 states), 429 quota backoff up to 90 s, exponential backoff, and degraded fallback retrieval unit-tested in `tests/test_guardrails_breaker.py`.
- **A6 (Agent Operational Metrics):** `Historical evidence available`. Prometheus metrics tracking tasks, steps, tool calls, and run durations per agent implemented and configured; live export blocked by Docker daemon.
- **A7 (Worker Scaling):** `Historical evidence available`. `--scale researcher=3 --scale assessor=3` empirically evaluated in `loadtest/results/scaled_3x.md`; p95 dropped from 75 s to 30 s at 16 users; live rerun blocked by Docker daemon.
- **A8 (Web Client UI):** `Historical evidence available`. Single-page web UI at `src/bpc/api/static/index.html` with preset test cases, live polling, and collapsible citations; live browser serving blocked by Docker daemon.

### Section 4.1 Reference Case (Section 4.1)
- **S4.1 (Difficult Case):** `Historical evidence available`. Residential building on small plot (108 sq.m) abutting narrow road (6 m) with 12.5 m height. Empirically retrieved Table 10 Note (ii)(b) (height capped at 11.5 m on roads $<9$ m) and Table 9 setbacks in `eval/results/real_S01.json`; routes accurately to `revise-and-recheck`. AST math and routing reproduced locally in pure Python with 100% agreement.

### LLMOps Requirements (L1 – L6)
- **L1 (Retrieval & Chunking):** `Unit-tested`. Structure-aware chunking with context headers unit-tested in `tests/test_chunking.py`; single-document in-place re-embedding (`--reembed`) verified.
- **L2 (Prompt Versioning):** `Historical evidence available`. Versioned YAML prompts with SHA8 content hashes; tag recorded on every call, span, and DB event. Empirical v1 vs v2 comparison documented in `eval/results/real_v1_part2.json` vs `real_v2_part2.json`.
- **L3 (Fixed Evaluation Set):** `Historical evidence available`. 22 scenarios ($\ge 20$) with expected outcomes and gold passages; modifier ablation comparison verified against raw JSONs (`eval/results/compare_real_v2_vs_real_nomod.md`).
- **L4 (Guardrails & Defenses):** `Unit-tested`. Input injection screening, XML spotlighting for free text, output filter, client ID spoofing defense, and toxicity checks unit-tested in `tests/test_guardrails_breaker.py`. Limitation: relies on regex heuristics.
- **L5 (Token & Cost Accounting):** `Historical evidence available`. Per-call tokens and dollar costs recorded by agent and step; projected cost per 100 runs (~$0.36); verified against checked-in JSON logs.
- **L6 (Feedback & Online Evaluation):** `Unit-tested`. Feedback schema and toxicity screening unit-tested; online eval sampling (`ONLINE_EVAL_SAMPLE_RATE`) historical evidence in DB migrations and worker code.

### Platform Requirements (D1 – D8)
- **D1 (Published Data Contracts):** `Unit-tested`. Strict Pydantic models; exported schemas in exact sync; served via API.
- **D2 (Idempotent Corpus Pipeline):** `Historical evidence available`. Idempotent ingestion (0 chunks changed on clean rerun); freshness and throughput metrics instrumented; live full corpus re-indexing blocked by Docker daemon.
- **D3 (Compose Stack):** `Blocked by the environment`. 16 services; non-root user enforcement; healthchecks on core DAG. `docker compose config` validates syntax-cleanly; live container launch blocked by Windows Docker daemon.
- **D4 (Secrets & Provider Hygiene):** `Unit-tested`. Zero committed keys confirmed by regex git grep audit; passwords generated at first start; `.env` git-ignored; generic model placeholders throughout.
- **D5 (Observability & Trace Reconstruction):** `Historical evidence available`. OpenTelemetry tracing across HTTP & Redis queues; 32-panel Grafana dashboard; full run replay logic in code; live scraping blocked by Docker daemon.
- **D6 (Predeclared p95 SLO):** `Historical evidence available`. Predeclared p95 $\le 45$ s; end-to-end submit-to-result load testing; concurrency bottleneck identified; historical CSV logs preserved.
- **D7 (Caching & Rate Limiting):** `Unit-tested`. 4 cache tiers (whole-run, LLM, retrieval, embedding); per-client sliding window rate limiting with bounded in-memory fallback on Redis failure unit-tested in `tests/test_guardrails_breaker.py`.
- **D8 (Runbook & Incident Log):** `Historical evidence available`. Two primary failure modes documented with recovery commands; 8 authentic incident post-mortems and rehearsal logs recorded in `docs/runbook.md` and `docs/incident_log.md`.

### Ten Required Demonstration Items
1. Clean-clone Compose startup: `Blocked by the environment` (host Windows Docker Desktop daemon stopped; `docker compose config` syntax valid).
2. Valid proposal producing cited recommendation: `Historical evidence available` (recorded in `eval/results/real_S01.json`; verified locally via pure Python reproduction and unit test suite).
3. End-to-end run trace reconstruction: `Historical evidence available` (trace schema and logic verified in code; empirical traces in `eval/results/*.json`).
4. Malformed request quarantined (no agent run): `Unit-tested` (`tests/test_contracts.py`; pure Python guarantees enqueue is unreachable on validation error).
5. Out-of-corpus case escalation: `Historical evidence available` (Scenario S14 in eval logs; routing logic unit-tested in `tests/test_verify_router.py`).
6. Self-verification catches unsupported answer: `Unit-tested` (`tests/test_verify_router.py::test_unresolved_citation_and_fabricated_quote_fail`).
7. Prompt-injection defense: `Unit-tested` (`tests/test_guardrails_breaker.py::test_injection_detected`, Scenario S15 in eval logs).
8. Circuit breaker opening during outage: `Unit-tested` (`tests/test_guardrails_breaker.py::test_breaker_opens_and_half_opens`).
9. Locust results vs SLO and `--scale`: `Historical evidence available` (documented in `loadtest/results/base_1x.md` and `scaled_3x.md` with raw CSVs).
10. Section 4.1 difficult reference case: `Historical evidence available` (both Table 10 Note (ii)(b) and Table 9 cited; AST math and routing unit-tested).

---

## 4. Top Confirmed Risks and Top Verified Strengths

### Top Verified Strengths
1. **Quarantine Isolation:** It is structurally impossible for a malformed or toxic request to trigger an agent run or enqueue a Redis job.
2. **Deterministic Precedence & Verification:** Compliance determinations and legal precedence (RMP-2015 ZR overrides BBL2003) are enforced by pure Python code, never left to LLM discretion.
3. **Resilience & Budget Fallback:** Gateway circuit breaker absorbs 429 quota bursts; rate limiter falls back to a bounded in-memory sliding window during Redis outages, preserving model budget protection.
4. **Reproducible Empirical Provenance:** All 18+ raw evaluation JSONs and load test CSVs match documented report figures without alteration.

### Top Confirmed Risks & Residual Gaps
1. **Regex-Based Guardrail Heuristics:** Toxicity and injection defenses rely on regular expression matching. Leetspeak, spacing, and indirect injection techniques can bypass the regex, falling back solely on XML spotlighting.
2. **Docker Socket Mount in `docker-stats`:** Mounts `/var/run/docker.sock` as root to collect container metrics on Docker Desktop, creating a privilege escalation surface if the container were compromised.
3. **Throughput Deficit Under Default Concurrency:** At default worker concurrency (4 slots), throughput peaks at 0.20 runs/s, requiring 3x worker scaling (`--scale researcher=3 --scale assessor=3`) to handle multi-user load.

---

## 5. Baseline vs Final Test Outcomes

| Suite / Check | Baseline Outcome | Final Remediation Outcome | Notes |
|---|---|---|---|
| Unit & Regression Tests | 25 PASSED (4.77 s) | **35 PASSED (3.94 s)** | +10 regression and robustness tests added for fixed defects |
| Whitespace & Git Diff | Passed | **PASSED (`git diff --check`)** | Zero trailing whitespace or CRLF warnings |
| Contract Sync | 5 Schemas in Sync | **5 Schemas in Sync** | Verified via `scripts/export_contracts.py` |
| Docker Compose Config | Valid (16 services) | **Valid (16 services)** | Validated via `docker compose config` |

---

## 6. What Changed and What Was Retained

### What Changed
- **`src/bpc/api/main.py`:**
  - Implemented bounded in-memory sliding-window fallback rate limiter (`_check_local_rate_limit`) on Redis connection error, preserving model budget protection (OPS-004).
  - Protected internal rate-limit override roles (`loadtest`, `eval`) from remote IP spoofing (SEC-003).
  - Screened feedback input for toxicity before database insertion (SEC-004).
- **`src/bpc/agents/runtime.py`:**
  - Hardened `parse_json` with string literal masking (`_strip_trailing_commas`) so trailing comma recovery never mutates commas, braces, or brackets inside strings (ROB-001, ROB-002).
- **`src/bpc/agents/verify.py`:**
  - Enforced comparison operator presence for numeric findings (VER-001).
  - Raised verbatim quote minimum length to 10 chars (VER-002).
  - Included derivation mismatches and unparseable formulas in hallucination accounting (VER-003).
- **`src/bpc/common/db.py` & `src/bpc/agents/worker.py`:**
  - Added terminal state precondition (`guard_terminal=True`) to prevent trailing worker overwrites on terminal runs (OPS-003).
- **Documentation Hygiene:**
  - Scrubbed hardcoded Google endpoints and model names from active documentation and markdown comparison files to comply with D4.
  - Reconciled runbook reaper deadline to 900 s.
  - Clarified hybrid modifier search architecture (combining deterministic safety net with model reflection).
- **Tests Added (+10 tests):**
  - Missing comparison operator fails verification (`test_missing_comparison_operator_fails_verification`).
  - Short quote (<10 chars) fails verification (`test_short_quote_under_10_chars_fails_verification`).
  - Derivation mismatch counted as hallucination (`test_derivation_mismatch_counted_as_hallucination`).
  - Trailing comma JSON recovery (`test_parse_json_trailing_comma`).
  - String literals containing commas and braces preserved intact (`test_parse_json_preserves_strings_with_commas_and_braces`).
  - Malformed JSON safely returns `None` (`test_parse_json_malformed_returns_none`).
  - Client ID override spoofing protection (`test_client_id_override_protection`).
  - Feedback toxicity screening (`test_screen_text_toxic_feedback`).
  - Redis error falls back to bounded in-memory rate limiter (`test_rate_limiter_redis_error_falls_back_to_in_memory`).
  - Rate limit override privilege validation (`test_rate_limit_override_privilege`).

### What Was Retained
- **All Raw Evaluation JSON Logs & Load Test CSVs:** Zero raw records modified or deleted. Only markdown comparison documents were sanitized. All 18+ raw evaluation files preserve exact provenance.

---

## 7. Performance, SLO, Evaluation, and Cost Summary

- **SLO Target:** p95 submit-to-result $\le 45$ s at up to 1 run/s (declared upfront in `docs/slo.md`).
- **Load Test Facts:** Baseline (1 replica, 4 slots) achieves 0.20 runs/s and meets SLO up to 8 users (35 s), failing at 16 users (75 s). 3x scaling (12 slots) restores SLO compliance at 16 users (30 s p95).
- **Caching Facts:** Whole-run cache drops p95 to 34 ms with 0 tokens. LLM response cache drops p95 to 1.1 s with 96% token reduction.
- **Evaluation Facts:** L2 Prompt v2 achieved 1.0000 groundedness and 0.0000 hallucination on Slice 2. L3 modifier ablation confirmed that disabling reflection causes route accuracy to fall from 0.8182 to 0.6364 across paired non-degraded scenarios ($n=11$).
- **Cost Facts:** Research tool loop dominates token usage (75%). Context compaction cut prompt tokens from 30.1k to 23.1k per run (-23%), yielding a projected cost of ~$0.36 per 100 runs.
