# Requirements Traceability Matrix

**Course:** UE24AM342AA5 — ML System Design and AgentOps  
**Project:** Mini Project 05 — Building Plan Compliance Pre-Check Service  
**Audit Branch:** `audit/mini-project-05-requirement-alignment`  
**Status Key (Strict 5-Category Taxonomy):**
- `Unit-tested`: Verified by automated local unit, contract, or regression tests in the current audit environment.
- `Historical evidence available`: Implemented and substantiated by checked-in historical evaluation logs, traces, or benchmarks; not rerun live due to environment/cost constraints.
- `Currently integration-tested`: Verified by active end-to-end integration tests connecting multiple live services in the current audit session.
- `Blocked by the environment`: Implemented in code/compose, but execution blocked by host environment constraints (e.g. stopped Windows Docker daemon).
- `Not verified or not implemented`: Not verified against specification or missing implementation.

---

## 1. Functional Requirements (F1 – F8)

| Req ID | Requirement | Status | Primary Implementation | Tests & Verification | Operational Notes |
|:---:|:---|:---:|:---|:---|:---|
| **F1** | Published REST Interface & Data Contract | **Unit-tested** | `src/bpc/api/main.py:183–415`, `src/bpc/common/contracts.py`, `contracts/*.schema.json` | `tests/test_contracts.py`, `scripts/export_contracts.py` | JSON Schemas served at `/v1/contracts/{name}`; verified schema sync; live HTTP serving blocked by Docker daemon. |
| **F2** | Ingestion Validation & Quarantine | **Unit-tested** | `src/bpc/api/main.py:168–206`, `src/bpc/common/contracts.py:180–248`, PostgreSQL `quarantine` table | `tests/test_contracts.py::test_cross_field_area_and_setbacks`, `tests/test_contracts.py::test_schema_errors_are_field_level` | Rejections produce HTTP 422 with field-level errors; code guarantees 0 runs enqueued; Postgres insert historical evidence in migrations. |
| **F3** | Classification & Entity Extraction | **Historical evidence available** | `src/bpc/agents/researcher.py:159–188`, `prompts/researcher.classify.v1.yaml` | `tests/test_contracts.py::test_multi_dwelling_requires_multi_use`, `eval/results/real_S01.json` | Classifies zone/use into 4 categories; extracts spatial entities; live LLM invocation not rerun to preserve API cost boundary. |
| **F4** | Retrieval of Binding Provisions | **Unit-tested** | `src/bpc/agents/researcher.py:288–338, 407–458`, `src/bpc/retriever/chunking.py` | `tests/test_chunking.py`, `tests/test_researcher_select.py` | Structure-aware chunking preserving tables and footnote clauses verified by `test_chunking.py`; live hybrid retriever service blocked by Docker. |
| **F5** | Cited Compliance Findings | **Unit-tested** | `src/bpc/agents/assessor.py:105–118`, `src/bpc/agents/verify.py:161–239` | `tests/test_verify_router.py` (16 tests) | Per-provision findings with clause label, page, verbatim quote, and passage text unit-tested; live assessor agent run historical in `eval/results/`. |
| **F6** | Three Recommendation Routes | **Unit-tested** | `src/bpc/agents/router.py:16–23, 47–101`, `src/bpc/common/contracts.py:81–85` | `tests/test_verify_router.py::test_route_clear_revise_specialist` | Strictly maps to `clear-for-submission`, `revise-and-recheck`, or `specialist-review`. |
| **F7** | Safe Escalation Boundary | **Unit-tested** | `src/bpc/agents/router.py:67–98`, `src/bpc/common/guardrails.py:104–125` | `tests/test_verify_router.py::test_unresolved_conflict_escalates` | Escalates on unresolvable conflicts, exemptions, out-of-corpus, injection, or degraded mode. |
| **F8** | Health, Metrics & Structured Logs | **Historical evidence available** | `src/bpc/api/main.py:417–464`, `src/bpc/common/observability.py`, `observability/prometheus.yml` | Prometheus scrape config, OpenTelemetry setup in code | `/health` checks state stores; Prometheus metrics on all components; JSON logs with run IDs; live scrape blocked by Docker daemon. |

---

## 2. Agent System Requirements (A1 – A8)

| Req ID | Requirement | Status | Primary Implementation | Tests & Verification | Operational Notes |
|:---:|:---|:---:|:---|:---|:---|
| **A1** | LangGraph Reasoning & Tools | **Unit-tested** | `src/bpc/agents/researcher.py`, `src/bpc/agents/assessor.py`, `src/bpc/agents/runtime.py` | `tests/test_researcher_select.py`, `tests/test_verify_router.py` | LangGraph state transitions and selection loops unit-tested; bounded by turns (14), tool calls (24), wall clock (420s); live LLM loop historical. |
| **A2** | Multi-Agent Separation & Hand-Off | **Historical evidence available** | `docker-compose.yml:190–213`, `src/bpc/agents/worker.py`, `src/bpc/common/queue.py` | `eval/results/real_S01.json`, `docs/architecture.md` | Two separate worker containers consuming distinct Redis queues (`q:research`, `q:assess`); lease reapers; live multi-container execution blocked by Docker daemon. |
| **A3** | Self-Verification Before Return | **Unit-tested** | `src/bpc/agents/verify.py`, `src/bpc/agents/assessor.py:121–156` | `tests/test_verify_router.py` (all 16 tests) | Deterministic AST math verification, verbatim quote check, status consistency, comparison operators, and single retry before withholding. |
| **A4** | Asynchronous Execution (202 + Poll) | **Historical evidence available** | `src/bpc/api/main.py:183–278`, `src/bpc/api/static/index.html` | `eval/results/*.json`, `smoke.py::submit`, `loadtest/locustfile.py` | POST returns HTTP 202 with `poll_after_s: 2.0`; background worker queue; state stored in Postgres; live HTTP poll blocked by Docker daemon. |
| **A5** | Timeouts, Backoff & Circuit Breaker | **Unit-tested** | `src/bpc/gateway/main.py`, `src/bpc/gateway/breaker.py`, `src/bpc/agents/researcher.py` | `tests/test_guardrails_breaker.py::test_breaker_opens_and_half_opens` | 3-state circuit breaker per provider unit-tested; 429 quota handling; exponential backoff; degraded mode. |
| **A6** | Per-Agent Operational Metrics | **Historical evidence available** | `src/bpc/agents/runtime.py:26–43`, `src/bpc/agents/worker.py:186–214` | Prometheus metrics instruments, Grafana `observability/grafana/dashboards/bpc.json` | Prometheus metrics for tasks, steps, tool calls, run seconds, and retries per agent; live scraping blocked by Docker daemon. |
| **A7** | Worker Scaling (`--scale`) | **Historical evidence available** | `docker-compose.yml:1–6`, `observability/prometheus.yml`, `docs/loadtest.md` | `loadtest/results/scaled_3x.md`, `loadtest/results/scaled_3x_stats.csv` | Empirically verified with 3x scale; p95 dropped from 75s to 30s at 16 users; live rerun blocked by Docker daemon. |
| **A8** | Web Client Interface | **Historical evidence available** | `src/bpc/api/static/index.html` | Static file inspection, API router integration | Single-page UI with preset scenarios, async polling, 422 error display, and citations; live browser access blocked by Docker daemon. |

---

## 3. Section 4.1 Difficult Reference Case

| Case ID | Description | Status | Evidence & Traceability | Notes |
|:---:|:---|:---:|:---|:---|
| **S4.1** | Residential building on small plot abutting narrow road | **Historical evidence available** | `eval/results/real_S01.json`, `docs/reference_case.md`, `eval/examples/reference_case.json` | Pure Python AST/router logic reproduced with 100% agreement (`revise-and-recheck`, 0 errors); historical execution in `eval/results/real_S01.json` retrieved and cited Table 10 Note (ii)(b) (height cap on road $<9\text{ m}$) and Table 9 setbacks; live run blocked by Docker daemon. |

---

## 4. LLMOps Requirements (L1 – L6)

| Req ID | Requirement | Status | Primary Implementation | Tests & Verification | Operational Notes |
|:---:|:---|:---:|:---|:---|:---|
| **L1** | Chunking, Indexing & Re-Embedding | **Unit-tested** | `src/bpc/retriever/chunking.py`, `src/bpc/retriever/ingest.py`, `src/bpc/retriever/store.py` | `tests/test_chunking.py`, `src/bpc/retriever/ingest.py --reembed` | Structure-aware chunking preserving tables and footnote clauses unit-tested; single-document re-embedding pipeline verified; live vector search blocked by Docker. |
| **L2** | Prompt Versioning & Comparison | **Historical evidence available** | `prompts/*.yaml`, `src/bpc/common/prompts.py`, `docs/l2_prompt_comparison.md` | `eval/results/real_v1_part2.json` vs `eval/results/real_v2_part2.json` | Content-hashed prompt tags (`prompt@v2#sha8`); empirical v1 vs v2 comparison documented on Slice 2; not rerun live to avoid cloud API cost. |
| **L3** | Fixed Evaluation Set & Deliberate Change | **Historical evidence available** | `eval/scenarios.yaml`, `src/bpc/evaluation/run_eval.py`, `docs/l3_modifier_analysis.md` | `eval/results/compare_real_v2_vs_real_nomod.md`, raw JSONs | 22 fixed scenarios ($\ge 20$); 4 explicit metric formulas; modifier on vs off comparison ($n=4$ paired Slice 3, $n=11$ cross-slice) preserved in raw JSONs. |
| **L4** | Guardrails (Injection, Toxicity, Output) | **Unit-tested** | `src/bpc/common/guardrails.py`, `src/bpc/api/main.py:141–145, 336–338` | `tests/test_guardrails_breaker.py` (5 tests) | Input injection detection, benign text pass, feedback toxicity, client ID spoofing defense, and output determination filtering unit-tested. Limitation: relies on regex heuristics. |
| **L5** | Token & Cost Accounting | **Historical evidence available** | `src/bpc/gateway/main.py:276–295`, `src/bpc/api/main.py:365–401` | `/v1/admin/cost-report`, `eval/results/*.json` | Tokens and costs recorded by agent and step at call time; projected cost per 100 runs (~$0.36); historical JSON logs preserve exact token/cost fields. |
| **L6** | Feedback API & Online Evaluation | **Unit-tested** | `src/bpc/api/main.py:321–340`, `src/bpc/agents/worker.py:238–255` | `tests/test_guardrails_breaker.py::test_screen_text_toxic_feedback`, `tests/test_contracts.py` | Feedback schema and toxicity screening unit-tested; DB persistence and online eval sampling (`ONLINE_EVAL_SAMPLE_RATE`) historical evidence in DB migrations and worker code. |

---

## 5. Platform and Deployment Requirements (D1 – D8)

| Req ID | Requirement | Status | Primary Implementation | Tests & Verification | Operational Notes |
|:---:|:---|:---:|:---|:---|:---|
| **D1** | Published Data Contracts | **Unit-tested** | `contracts/*.schema.json`, `docs/data_contract.md`, `src/bpc/common/contracts.py` | `scripts/export_contracts.py`, `tests/test_contracts.py` | Strict Pydantic models; exported JSON Schemas in exact sync; served via API contract endpoint. |
| **D2** | Idempotent Corpus Pipeline | **Historical evidence available** | `src/bpc/retriever/ingest.py`, `corpus/manifest.yaml` | `src/bpc/retriever/ingest.py`, `tests/test_chunking.py` | Idempotent (0 chunks changed on rerun); manifest hashes and throughput instrumented; full pipeline live run blocked by Docker daemon. |
| **D3** | Compose Stack & Services ($\ge 4$) | **Blocked by the environment** | `docker-compose.yml`, `docker/Dockerfile.*` | `docker compose config` passes (16 services) | Full stack defined with 16 services, non-root user enforcement, healthchecks on core DAG; live container launch blocked by Windows Docker daemon. |
| **D4** | Secrets & Provider Configuration | **Unit-tested** | `docker-compose.yml:secrets-init`, `.env.example`, `src/bpc/common/config.py` | Regex git grep audits, `tests/test_guardrails_breaker.py` | Zero committed keys in git; random passwords generated at first start; `.env` git-ignored; generic model placeholders throughout. |
| **D5** | Tracing, Metrics & Run Reconstruction | **Historical evidence available** | `src/bpc/common/observability.py`, `src/bpc/api/main.py:trace`, Grafana dashboard | `GET /v1/runs/{id}/trace`, OpenTelemetry setup | OpenTelemetry tracing across HTTP & Redis queues; 32-panel Grafana dashboard; full run replay logic in code; live Jaeger/Prometheus blocked by Docker. |
| **D6** | Predeclared p95 SLO & Locust Benchmark | **Historical evidence available** | `docs/slo.md`, `loadtest/locustfile.py`, `docs/loadtest.md` | `loadtest/results/base_1x.md`, `loadtest/results/scaled_3x.md` | Predeclared p95 $\le 45$ s; end-to-end submit-to-result load testing; concurrency bottleneck identified; historical CSV logs preserved. |
| **D7** | Caching & Rate Limiting | **Unit-tested** | `src/bpc/api/main.py:148–190`, `src/bpc/gateway/main.py`, Redis & Postgres | `tests/test_guardrails_breaker.py` (rate limit fallback & privilege tests) | 4 cache tiers (whole-run, LLM, retrieval, embedding); per-client sliding window rate limiting with bounded in-memory fallback on Redis outage unit-tested. |
| **D8** | Runbook & Incident Log | **Historical evidence available** | `docs/runbook.md`, `docs/incident_log.md` | Checked-in markdown documentation | Two primary failure modes documented with recovery commands; 8 authentic incident post-mortems and rehearsal logs recorded. |

---

## 6. Ten Required Demonstration Items (Section 2.7 Brief)

| # | Required Demonstration Item | Status | Verification Command / Click Path | Evidence Captured |
|:---:|:---|:---:|:---|:---|
| **1** | Clean-clone `docker compose up` | **Blocked by the environment** | `docker compose config` (valid); live execution blocked by Windows host Docker daemon. | Docker Compose configuration validated without errors (16 services). |
| **2** | Valid request produces routed cited recommendation | **Historical evidence available** | `eval/results/real_S01.json`, local Python reproduction | Route, findings, and citations resolve directly to retrieved text; verified locally in pure Python. |
| **3** | End-to-end run trace reconstruction | **Historical evidence available** | `eval/results/real_S01.json`, `GET /v1/runs/{id}/trace` logic | Full trace schema with tool calls, queries, passages, prompt versions, and step latencies preserved in historical logs. |
| **4** | Malformed request quarantined (no agent run) | **Unit-tested** | `tests/test_contracts.py`, `src/bpc/api/main.py:168–206` | HTTP 422 returned; field-level errors; code guarantees enqueue is unreachable. |
| **5** | Out-of-corpus case escalates safely | **Historical evidence available** | `eval/results/dev/real_v1.json` (Scenario S14), `tests/test_verify_router.py` | Routes to `specialist-review` with reason stating out-of-corpus jurisdiction. |
| **6** | Verification catches unsupported answer & retries | **Unit-tested** | `tests/test_verify_router.py::test_unresolved_citation_and_fabricated_quote_fail` | Verifier catches unresolved citations/quotes; withholds findings; escalates. |
| **7** | Prompt-injection attempt and guardrail response | **Unit-tested** | `tests/test_guardrails_breaker.py::test_injection_detected`, Scenario S15 in eval logs | Prompt injection flagged; notes withheld; routes to `specialist-review`. |
| **8** | Circuit breaker opens during outage & degrades | **Unit-tested** | `tests/test_guardrails_breaker.py::test_breaker_opens_and_half_opens` | Breaker trips after threshold; enters half-open on cooldown; resets on success. |
| **9** | Locust results against SLO & effect of `--scale` | **Historical evidence available** | `loadtest/results/base_1x.md` vs `loadtest/results/scaled_3x.md` | p95 latency at 16 users dropped from 75s to 30s under 3x worker scaling; raw CSVs preserved. |
| **10**| Section 4.1 difficult reference case | **Historical evidence available** | `eval/results/real_S01.json`, `docs/reference_case.md` | Table 10 Note (ii)(b) and Table 9 both retrieved and cited; routes `revise-and-recheck`; AST math verified locally. |
