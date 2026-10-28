# Reconciled Findings & Requirements Register

**Audit Branch:** `audit/mini-project-05-requirement-alignment`  
**Review Dates:** 2026-10-28  
**Auditors:** Reviewer A (Requirements & Architecture), Reviewer B (Grounding & Security), Reviewer C (LLMOps & Evaluation), Reviewer D (Runtime & Observability), Reviewer E (Adversarial Maintainer)

---

## 1. Severity Guidelines

- **P0 BLOCKER:** System cannot perform the required baseline; destructive data loss; secret exposure; severe unsafe determination.
- **P1 CRITICAL:** Core requirement or safety boundary materially broken (e.g. fabricated legal conclusion, unresolved citation, failure to isolate malformed input).
- **P2 HIGH:** Substantial correctness, reliability, evaluation validity, security, or reproducibility problem.
- **P3 MEDIUM:** Non-blocking functional gap, important docs/test/observability weakness, or maintainability risk.
- **P4 LOW / INFO:** Minor cleanup, documentation hygiene, or verified architectural observation.

---

## 2. Reconciled Findings Register

### [SEC-001] Specific Cloud Provider Endpoints and Model IDs Committed in Docs/Eval Results
- **Requirement ID:** D4
- **Severity:** P1 CRITICAL
- **Confidence:** CONFIRMED
- **Independent Reviewers:** Reviewer E, Reviewer D
- **File & Line:** `docs/l2_prompt_comparison.md:5`, `docs/l3_modifier_analysis.md:5`, `eval/results/compare_real_v2_vs_real_nomod.md:5, 18`, `docs/runbook.md:120`
- **Concrete Evidence:**
  The literal provider URL `https://generativelanguage.googleapis.com/v1beta/openai` and model ID `gemini-3.5-flash-lite` were committed in documentation files, directly contradicting D4 and `docs/report.md`'s assertion that *"No LLM model id, provider endpoint or credential is in the repository"*.
  **Historical Data Provenance Audit:** A complete byte-level audit of all 18+ raw evaluation JSON files (`eval/results/*.json`) confirmed that raw evaluation records never contained vendor URLs or API keys; they record scenario IDs, prompt version hashes, status, latency, route, cost, tokens, and verification details. Zero raw `.json` evaluation logs were modified or deleted.
- **Impact:** Violates Requirement D4 and introduces documentation contradictions regarding model-agnostic neutrality.
- **Minimal Fix:** Replaced hardcoded provider endpoints and model names with generic environment-injected placeholders (`$LLM_PRIMARY_MODEL` at `$LLM_PRIMARY_BASE_URL`). Sanitized residual provider free-tier mentions in markdown comparison files.
- **Regression Test / Verification:** `git grep -iE "googleapis\.com|flash-lite"` returns 0 occurrences across active documentation.
- **Disposition:** RESOLVED.

---

### [SEC-002] Docker Socket Mounted as Root in `docker-stats` Container
- **Requirement ID:** D3, D4
- **Severity:** P2 HIGH
- **Confidence:** CONFIRMED
- **Independent Reviewers:** Reviewer B, Reviewer E
- **File & Line:** `docker-compose.yml:248-256`, `src/bpc/dockerstats/main.py:44`
- **Concrete Evidence:**
  `docker-stats` executes with `user: root` and mounts `/var/run/docker.sock:/var/run/docker.sock:ro`.
- **Impact:** While `:ro` protects directory inode modifications, stream socket communication permits HTTP requests to the Docker daemon (such as `/containers/{id}/json`), exposing container environment configurations.
- **Minimal Fix:** Documented as an intentional operational trade-off required for local Docker Desktop environments (where cAdvisor fails on containerd storage, INC-003). For production, deploy `tecnativa/docker-socket-proxy` restricted strictly to `GET /containers/{id}/stats`.
- **Disposition:** ACCEPTED WITH DOCUMENTATION.

---

### [SEC-003] Remote Client Spoofing of Internal Rate-Limit Overrides
- **Requirement ID:** D7
- **Severity:** P2 HIGH
- **Confidence:** CONFIRMED
- **Independent Reviewers:** Reviewer D, Reviewer E
- **File & Line:** `src/bpc/api/main.py:137-141`
- **Concrete Evidence:**
  `_client_id` accepted any user-supplied `X-Client-Id` header (e.g., `X-Client-Id: loadtest`), granting 100,000 req/min without authentication.
- **Impact:** External untrusted clients could bypass the default 20 req/min rate limit by sending spoofed override headers.
- **Minimal Fix:** Restricted high-rate override roles (`loadtest`, `eval`) in `_client_id` to localhost/internal IPs (`127.0.0.1`, `localhost`, `::1`, `testclient`). Remote clients claiming these roles are namespaced with their IP address (`loadtest:<ip>`).
- **Regression Test:** `tests/test_guardrails_breaker.py::test_client_id_override_protection` verifies remote spoofing isolation.
- **Disposition:** RESOLVED.

---

### [SEC-004] User Feedback Endpoint Missing Input Toxicity Screen
- **Requirement ID:** L4, L6
- **Severity:** P3 MEDIUM
- **Confidence:** CONFIRMED
- **Independent Reviewers:** Reviewer B
- **File & Line:** `src/bpc/api/main.py:321-330`
- **Concrete Evidence:**
  `POST /v1/runs/{id}/feedback` inserted `body.reason` directly into PostgreSQL without screening for abusive or toxic language.
- **Impact:** Abusive feedback text could be stored and surfaced in administrative summary endpoints.
- **Minimal Fix:** Added `screen_text(body.reason)` validation in `api/main.py:feedback`; returns HTTP 422 if toxic.
- **Regression Test:** `tests/test_guardrails_breaker.py::test_screen_text_toxic_feedback`.
- **Disposition:** RESOLVED.

---

### [OPS-001] Ingestion Crash on Transient Redis Disconnection & Rate Limiter Budget Protection
- **Requirement ID:** A5, D7
- **Severity:** P2 HIGH
- **Confidence:** CONFIRMED
- **Independent Reviewers:** Reviewer D, Reviewer E
- **File & Line:** `src/bpc/api/main.py:148-189`
- **Concrete Evidence:**
  `_rate_limited` originally invoked `await S.redis.incr(key)` without exception handling. A Redis timeout or restart triggered an unhandled exception resulting in HTTP 500 crashes on all incoming proposals. While a naive `try/except` returning `None` (fail-open) prevented crashes, failing open silently dismantled model budget and concurrency protections during Redis outages.
- **Impact:** Total denial of service during Redis errors if unhandled; or uncontrolled API flood and model budget exhaustion if failing open.
- **Minimal Fix:** Implemented a bounded in-memory sliding-window fallback rate limiter (`_check_local_rate_limit`) with window pruning. On Redis connection error or unavailability, the API logs a warning and enforces client rate limits locally in memory, returning HTTP 429 when limits are exceeded.
- **Regression Tests:** `tests/test_guardrails_breaker.py::test_rate_limiter_redis_error_falls_back_to_in_memory` and `tests/test_guardrails_breaker.py::test_rate_limit_override_privilege`.
- **Disposition:** RESOLVED.

---

### [OPS-002] Potential Race Condition in Non-Atomic Job Queue Leasing
- **Requirement ID:** A2, A5
- **Severity:** P2 HIGH
- **Confidence:** CONFIRMED
- **Independent Reviewers:** Reviewer D
- **File & Line:** `src/bpc/common/queue.py:33-38`
- **Concrete Evidence:**
  `JobQueue.get()` moves a job from `q:<name>` to `q:<name>:processing` via `BLMOVE`, yields to the asyncio loop, and then executes `SET lease:<job_id>`. A concurrent reaper running in that millisecond window could observe an unleased processing job.
- **Impact:** Could trigger an unexpected duplicate job retry during high worker concurrency.
- **Minimal Fix:** In `worker.py:reaper()`, verified that reapers check lease expiration and only clean up after job timeouts; recommended combining into an atomic Redis pipeline or Lua script for high-load production.
- **Disposition:** MITIGATED & DOCUMENTED.

---

### [OPS-003] Run Updates Lack Terminal State Preconditions
- **Requirement ID:** A5
- **Severity:** P3 MEDIUM
- **Confidence:** CONFIRMED
- **Independent Reviewers:** Reviewer D
- **File & Line:** `src/bpc/common/db.py:143-150`, `src/bpc/agents/worker.py:226`
- **Concrete Evidence:**
  `update_run` executed unconditional `UPDATE runs SET ... WHERE run_id = $1`. If a run was marked `failed` by the global API deadline reaper, a slow trailing worker could overwrite the terminal failure state.
- **Impact:** Violation of state machine invariants; potential resurrection of reaped runs.
- **Minimal Fix:** Added `guard_terminal: bool = False` to `update_run`. When True, appends `AND status NOT IN ('completed', 'failed', 'escalated')`. Worker completion now passes `guard_terminal=True`.
- **Disposition:** RESOLVED.

---

### [OPS-004] Runbook Deadline Documentation Mismatch
- **Requirement ID:** D8
- **Severity:** P4 LOW
- **Confidence:** CONFIRMED
- **Independent Reviewers:** Reviewer D
- **File & Line:** `docs/runbook.md:48`
- **Concrete Evidence:**
  `docs/runbook.md` referenced a 300 s deadline, while `Settings.run_deadline_s` and `docker-compose.yml` configure a 900 s default.
- **Impact:** Minor operator confusion during incident triage.
- **Minimal Fix:** Reconciled `docs/runbook.md` to reference `RUN_DEADLINE_S (default 900 s)`.
- **Disposition:** RESOLVED.

---

### [VER-001] Status Consistency Check Skipped When Comparison Operator is Missing
- **Requirement ID:** A3, F5
- **Severity:** P2 HIGH
- **Confidence:** CONFIRMED
- **Independent Reviewers:** Reviewer B
- **File & Line:** `src/bpc/agents/verify.py:218-226`
- **Concrete Evidence:**
  `verify_findings` only checked numeric status consistency if `cmp in _CMP`. If an LLM emitted a finding with `status: "satisfied"` or `"violated"` but omitted `comparison` or passed an unrecognized string, the check was bypassed with zero errors recorded.
- **Impact:** Allowed unverified numeric determinations to bypass verification.
- **Minimal Fix:** Added validation requiring `cmp in _CMP` whenever `status` is satisfied/violated and both `req` and `prop` are numeric. Missing or invalid comparisons append `comparison_missing` and mark the finding as untraceable.
- **Regression Test:** `tests/test_verify_router.py::test_missing_comparison_operator_fails_verification`.
- **Disposition:** RESOLVED.

---

### [VER-002] Permissive Minimum Quote Length in Self-Verification
- **Requirement ID:** A3, F5
- **Severity:** P3 MEDIUM
- **Confidence:** CONFIRMED
- **Independent Reviewers:** Reviewer B
- **File & Line:** `src/bpc/agents/verify.py:181`
- **Concrete Evidence:**
  `len(normalise(quote)) < 6` permitted trivial words (e.g. `"height"`, `"ground"`) to satisfy the verbatim quotation check.
- **Impact:** Decreased quotation grounding rigor; models could quote isolated words instead of regulatory phrases.
- **Minimal Fix:** Increased minimum normalized quote length to 10 characters.
- **Regression Test:** `tests/test_verify_router.py::test_short_quote_under_10_chars_fails_verification`.
- **Disposition:** RESOLVED.

---

### [VER-003] Mathematical Derivation Contradictions Not Counted as Hallucinations
- **Requirement ID:** A3, L3
- **Severity:** P3 MEDIUM
- **Confidence:** CONFIRMED
- **Independent Reviewers:** Reviewer C
- **File & Line:** `src/bpc/agents/verify.py:198-202, 227-228`
- **Concrete Evidence:**
  When `derivation_mismatch` or `derivation_unparseable` occurred, errors were appended to `chk.errors`, but `untraceable = True` was not set, resulting in `hallucination_rate = 0.0`.
- **Impact:** Metric distortion: arithmetic fabrication was excluded from the reported hallucination rate.
- **Minimal Fix:** Set `untraceable = True` upon derivation mismatch or unparseable expression.
- **Regression Test:** `tests/test_verify_router.py::test_derivation_mismatch_counted_as_hallucination`.
- **Disposition:** RESOLVED.

---

### [ROB-001] Strict JSON Parser Fails on LLM Trailing Commas & String Mutation Risk
- **Requirement ID:** A1
- **Severity:** P2 HIGH
- **Confidence:** CONFIRMED
- **Independent Reviewers:** Reviewer E
- **File & Line:** `src/bpc/agents/runtime.py:132-175`
- **Concrete Evidence:**
  `parse_json` failed completely when LLMs emitted JSON with trailing commas (e.g., `{"a": 1,}`), returning `None` and causing silent classification or provision dropouts. A naive regex removal `re.sub(r",\s*([}\]])", r"\1", candidate)` introduced a severe string corruption defect: any string literal containing `,}` or `,]` (e.g., `"notes": "items: a, b, and c,}"`) was corrupted into `"notes": "items: a, b, and c}"`.
- **Impact:** Unnecessary verification retries and escalations from trailing commas; or silent mutation of legal citations and notes containing trailing punctuation.
- **Minimal Fix:** Implemented `_strip_trailing_commas` with double-quoted string literal masking (`r'"(?:[^"\\]|\\.)*"'`) before trailing comma removal, restoring masked string literals intact afterwards.
- **Regression Tests:** `tests/test_verify_router.py::test_parse_json_trailing_comma`, `tests/test_verify_router.py::test_parse_json_preserves_strings_with_commas_and_braces`, and `tests/test_verify_router.py::test_parse_json_malformed_returns_none`.
- **Disposition:** RESOLVED.

---

### [DOC-001] Clarification of Hybrid Modifier Search Architecture
- **Requirement ID:** F4, A1, Section 4.1
- **Severity:** P3 MEDIUM
- **Confidence:** CONFIRMED
- **Independent Reviewers:** Reviewer A, Reviewer E
- **File & Line:** `docs/report.md:88-94`, `docs/reference_case.md:61-64`, `docs/architecture.md:86-87`
- **Concrete Evidence:**
  `docs/report.md` described modifier search in terms suggesting pure model reflection, whereas `researcher.py:426` combines model reflection with a deterministic variable interaction safety net (`_variable_queries`).
- **Impact:** Discrepancy between engineering documentation and actual Python implementation.
- **Minimal Fix:** Updated `docs/report.md` and `docs/reference_case.md` to explicitly state that modifier search uses a hybrid design combining agent reflection with a deterministic variable interaction safety net.
- **Disposition:** RESOLVED.

---

### [EVAL-001] Metric Naming Inconsistency Between Offline and Online Evaluation
- **Requirement ID:** L3, L6
- **Severity:** P3 MEDIUM
- **Confidence:** CONFIRMED
- **Independent Reviewers:** Reviewer C, Reviewer E
- **File & Line:** `src/bpc/evaluation/run_eval.py:88` vs `src/bpc/agents/worker.py:247`
- **Concrete Evidence:**
  Offline `run_eval.py` computes context relevance as gold retrieval recall (`len(retrieved & gold) / len(gold)`), while online `worker.py` computes it as dossier utilization precision (`len(used) / n_ctx`).
- **Impact:** Operators comparing offline benchmark scores to online dashboard panels could be confused by identical metric names representing different mathematical formulas.
- **Minimal Fix:** Documented the distinction in audit reports and evaluation documentation.
- **Disposition:** DOCUMENTED.

---

## 3. Rejected and False-Positive Findings

1. **Claim: "Section 4.1 reference case values are fabricated because BBMP 2003 setbacks conflict with ZR2015."**  
   - *Status:* **REJECTED (FALSE POSITIVE).**  
   - *Evidence:* Precedence is an explicit, verified project assumption confirmed at Evaluation 1 (`corpus/manifest.yaml:3-7`). The BDA RMP-2015 Zoning Regulations govern setbacks, FAR, coverage, height, and use where both documents speak. Under ZR2015 §4.1.2 Table 10 Note (ii)(b), the road-width height limit of 11.5 m on roads $< 9.0$ m is authentic source text on page 28 of the checked-in PDF.

2. **Claim: "Quarantine boundary allows malformed requests to enqueue jobs."**  
   - *Status:* **REJECTED (DISPROVED BY CODE INSPECTION).**  
   - *Evidence:* In `src/bpc/api/main.py:204-206`, `validate_proposal` runs before any database run row is created or Redis message is published. If validation fails, the function executes `return await _quarantine(...)`. The enqueue call at line 253 is mathematically unreachable.
