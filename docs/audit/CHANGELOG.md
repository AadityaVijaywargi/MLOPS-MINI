# Audit Remediation Changelog

**Audit Branch:** `audit/mini-project-05-requirement-alignment`  
**Base Commit:** `b10680e` (master / aarav-yuval-evaluation)  
**Remediation Date:** 2026-10-28  

---

## Changes Grouped by Finding and Requirement ID

### 1. Verification & AST Math Hardening (VER-001, VER-002, VER-003 / Req: A3, F5)
- **Affected File:** `src/bpc/agents/verify.py`
- **Root Cause:**
  - Status consistency check was skipped if `comparison` was omitted or invalid in numeric findings.
  - Verbatim quote length threshold (6 chars) allowed single words (e.g. `"height"`) to pass verification.
  - Internal derivation mismatches were recorded as errors but excluded from the `hallucination_rate` calculation.
- **Changes Made:**
  - Added strict validation requiring `comparison in _CMP` for numeric findings with status `satisfied`/`violated`. If missing, appends `comparison_missing` and marks the finding as untraceable.
  - Increased minimum quote length to 10 characters (`len(normalise(quote)) < 10`).
  - Added `untraceable = True` when `derivation_mismatch` or `derivation_unparseable` occurs, ensuring arithmetic fabrications are reflected in the hallucination metric.
- **Tests Added / Run:**
  - `tests/test_verify_router.py::test_missing_comparison_operator_fails_verification` [PASS]
  - `tests/test_verify_router.py::test_short_quote_under_10_chars_fails_verification` [PASS]
  - `tests/test_verify_router.py::test_derivation_mismatch_counted_as_hallucination` [PASS]

---

### 2. Robust JSON Parsing Fallback (ROB-001 / Req: A1)
- **Affected File:** `src/bpc/agents/runtime.py`
- **Root Cause:**
  - LLMs occasionally emit JSON containing trailing commas before closing braces/brackets (`{"a": 1,}`). Standard `json.loads` fails on this syntax, returning `None` and triggering silent provision dropouts or verification retries.
- **Changes Made:**
  - Added a regex-based pre-cleaning fallback (`re.sub(r",\s*([}\]])", r"\1", candidate)`) when standard `json.loads` raises `JSONDecodeError`.
- **Tests Added / Run:**
  - `tests/test_verify_router.py::test_parse_json_trailing_comma` [PASS]

---

### 3. API Ingestion & Rate-Limit Resilience (OPS-001, SEC-003, SEC-004 / Req: A5, D7, L4, L6)
- **Affected File:** `src/bpc/api/main.py`
- **Root Cause:**
  - Unhandled Redis connection errors in `_rate_limited` crashed all incoming proposals with HTTP 500 errors.
  - Remote callers could spoof `X-Client-Id: loadtest` to acquire 100,000 req/min without authentication.
  - The feedback submission endpoint did not screen `reason` text for toxicity before database insertion.
- **Changes Made:**
  - Wrapped `_rate_limited` Redis calls in `try/except Exception`, logging a warning and failing open during transient Redis downtime.
  - Protected internal high-rate override client IDs (`loadtest`, `eval`) by namespacing with client IP if the request originates from a non-local address.
  - Added `screen_text(body.reason)` validation to `POST /v1/runs/{id}/feedback`, rejecting abusive content with HTTP 422.
- **Tests Added / Run:**
  - `tests/test_guardrails_breaker.py::test_client_id_override_protection` [PASS]
  - `tests/test_guardrails_breaker.py::test_screen_text_toxic_feedback` [PASS]

---

### 4. Database Concurrency & State Machine Precondition (OPS-003 / Req: A5)
- **Affected Files:** `src/bpc/common/db.py`, `src/bpc/agents/worker.py`
- **Root Cause:**
  - `update_run` executed unconditional SQL updates without checking whether the run was already marked terminal (`failed`) by the API deadline reaper.
- **Changes Made:**
  - Added `guard_terminal: bool = False` parameter to `update_run` which appends `AND status NOT IN ('completed', 'failed', 'escalated')`.
  - Updated `worker.py:assess` completion update to pass `guard_terminal=True`.
- **Tests Run:**
  - Full unit test suite passes with zero regressions.

---

### 5. D4 Secrets & Cloud Model Hygiene (SEC-001, OPS-004 / Req: D4, D8)
- **Affected Files:** `docs/l2_prompt_comparison.md`, `docs/l3_modifier_analysis.md`, `eval/results/compare_real_v2_vs_real_nomod.md`, `docs/runbook.md`
- **Root Cause:**
  - Cloud provider endpoints (`https://generativelanguage.googleapis.com/...`) and model names (`gemini-3.5-flash-lite`) were committed in documentation files, violating Requirement D4.
  - `docs/runbook.md` documented a 300 s deadline while configuration defaults to 900 s.
- **Changes Made:**
  - Scrubbed specific cloud URLs and model identifiers from markdown documents, replacing them with generic environment variable references (`$LLM_PRIMARY_MODEL` at `$LLM_PRIMARY_BASE_URL`).
  - Reconciled deadline documentation in `docs/runbook.md` to reference `RUN_DEADLINE_S (default 900 s)`.
- **Verification:**
  - `git grep -iE "googleapis\.com|flash-lite"` returns 0 results across active documentation.

---

### 6. Architectural Documentation Transparency (DOC-001 / Req: F4, A1, Section 4.1)
- **Affected Files:** `docs/report.md`, `docs/reference_case.md`
- **Root Cause:**
  - Documentation gave the impression that the modifier query `"maximum height of building restricted by road width"` was derived solely by emergent LLM reflection, whereas the code combines LLM reflection with a deterministic variable interaction safety net (`_variable_queries`).
- **Changes Made:**
  - Updated `docs/report.md` (§3) and `docs/reference_case.md` (§5) to explicitly describe the hybrid architecture combining agentic model reflection with deterministic combinatorial expansion.

---

## Summary of Test Results
- **Initial Baseline Suite:** 25 passed in 4.77 s.
- **Final Test Suite:** 31 passed in 4.45 s (+6 new regression tests).
- **Whitespace / Git Diff Check:** `git diff --check` passes with 0 errors.
