# Requirements Traceability Matrix

**Course:** UE24AM342AA5 — ML System Design and AgentOps  
**Project:** Mini Project 05 — Building Plan Compliance Pre-Check Service  
**Audit Branch:** `audit/mini-project-05-requirement-alignment`  
**Status Key:**
- `VERIFIED`: Confirmed by code-level inspection, execution, and unit/integration tests.
- `PARTIAL`: Core behavior implemented, but minor edge-case limitation exists.
- `BLOCKED`: Test execution blocked by host environment constraints (e.g. host Docker daemon).
- `NOT APPLICABLE`: Explicitly out of scope per assignment brief.

---

## 1. Functional Requirements (F1 – F8)

| Req ID | Requirement | Status | Primary Implementation | Tests & Verification | Operational Notes |
|:---:|:---|:---:|:---|:---|:---|
| **F1** | Published REST Interface & Data Contract | **VERIFIED** | `src/bpc/api/main.py:183–415`, `src/bpc/common/contracts.py`, `contracts/*.schema.json` | `tests/test_contracts.py`, `scripts/export_contracts.py` | JSON Schemas served at `/v1/contracts/{name}`; OpenAPI schema integration. |
| **F2** | Ingestion Validation & Quarantine | **VERIFIED** | `src/bpc/api/main.py:158–206`, `contracts.py:180–248`, PostgreSQL `quarantine` table | `tests/test_contracts.py::test_cross_field_area_and_setbacks`, `smoke.py::check_malformed` | Rejected requests return HTTP 422 with field-level errors; zero runs queued. |
| **F3** | Classification & Entity Extraction | **VERIFIED** | `src/bpc/agents/researcher.py:159–188`, `prompts/researcher.classify.v1.yaml` | `tests/test_contracts.py::test_multi_dwelling_requires_multi_use`, batch eval logs | Classifies zone/use into 4 categories; extracts spatial entities; screens exemption signals. |
| **F4** | Retrieval of Binding Provisions | **VERIFIED** | `src/bpc/agents/researcher.py:288–338, 407–458`, `retriever/chunking.py` | `tests/test_chunking.py`, `tests/test_researcher_select.py`, `docs/reference_case.md` | Hybrid dense (all-MiniLM-L6-v2) + BM25; structure-aware chunks with context headers. |
| **F5** | Cited Compliance Findings | **VERIFIED** | `src/bpc/agents/assessor.py:105–118`, `src/bpc/agents/verify.py:161–234` | `tests/test_verify_router.py::test_verbatim_quote_with_pdf_spacing_passes` | Per-provision findings with clause label, page, verbatim quote, and passage text. |
| **F6** | Three Recommendation Routes | **VERIFIED** | `src/bpc/agents/router.py:16–23, 47–101`, `src/bpc/common/contracts.py:81–85` | `tests/test_verify_router.py::test_route_clear_revise_specialist` | Strictly maps to `clear-for-submission`, `revise-and-recheck`, or `specialist-review`. |
| **F7** | Safe Escalation Boundary | **VERIFIED** | `src/bpc/agents/router.py:67–98`, `src/bpc/common/guardrails.py:104–125` | `tests/test_verify_router.py::test_unresolved_conflict_escalates` | Escalates on unresolvable conflicts, exemptions, out-of-corpus, injection, or degraded mode. |
| **F8** | Health, Metrics & Structured Logs | **VERIFIED** | `src/bpc/api/main.py:417–432`, `src/bpc/common/observability.py`, `observability/prometheus.yml` | Full test suite, Prometheus scrape config | `/health` checks state stores; Prometheus metrics on all components; JSON logs with run IDs. |

---

## 2. Agent System Requirements (A1 – A8)

| Req ID | Requirement | Status | Primary Implementation | Tests & Verification | Operational Notes |
|:---:|:---|:---:|:---|:---|:---|
| **A1** | LangGraph Reasoning & Tools | **VERIFIED** | `src/bpc/agents/researcher.py`, `src/bpc/agents/assessor.py`, `runtime.py` | `tests/test_researcher_select.py`, `tests/test_verify_router.py` | LangGraph state machines; 6 research tools; bounded by turns (14), tool calls (24), wall clock (420s). |
| **A2** | Multi-Agent Separation & Hand-Off | **VERIFIED** | `docker-compose.yml:190–213`, `src/bpc/agents/worker.py`, `src/bpc/common/queue.py` | `tests/test_guardrails_breaker.py`, `docs/architecture.md` | Two separate worker containers consuming distinct Redis queues (`q:research`, `q:assess`); lease reapers. |
| **A3** | Self-Verification Before Return | **VERIFIED** | `src/bpc/agents/verify.py`, `src/bpc/agents/assessor.py:121–156` | `tests/test_verify_router.py` (all 14 tests) | Deterministic AST math verification, verbatim quote check, status consistency, and single retry. |
| **A4** | Asynchronous Execution (202 + Poll) | **VERIFIED** | `src/bpc/api/main.py:183–278`, `src/bpc/api/static/index.html` | `smoke.py::submit`, `loadtest/locustfile.py` | POST returns HTTP 202 with `poll_after_s: 2.0`; background worker queue; state stored in Postgres. |
| **A5** | Timeouts, Backoff & Circuit Breaker | **VERIFIED** | `src/bpc/gateway/main.py`, `src/bpc/gateway/breaker.py`, `researcher.py:519–555` | `tests/test_guardrails_breaker.py::test_breaker_opens_and_half_opens` | 3-state circuit breaker per provider; 429 quota handling; exponential backoff; degraded mode. |
| **A6** | Per-Agent Operational Metrics | **VERIFIED** | `src/bpc/agents/runtime.py:26–43`, `src/bpc/agents/worker.py:186–214` | Prometheus configuration, Grafana `bpc.json` | Prometheus metrics for tasks, steps, tool calls, run seconds, and retries per agent. |
| **A7** | Worker Scaling (`--scale`) | **VERIFIED** | `docker-compose.yml:1–6`, `observability/prometheus.yml`, `docs/loadtest.md` | `loadtest/results/scaled_3x.md` | Empirically verified with 3x scale; p95 dropped from 75s to 30s at 16 users; bottleneck isolated. |
| **A8** | Web Client Interface | **VERIFIED** | `src/bpc/api/static/index.html` | Served at `/`, manual test path | Single-page UI with preset scenarios, async polling, 422 error display, and citations. |

---

## 3. Section 4.1 Difficult Reference Case

| Case ID | Description | Status | Evidence & Traceability | Notes |
|:---:|:---|:---:|:---|:---|
| **S4.1** | Residential building on small plot abutting narrow road | **VERIFIED** | `docs/reference_case.md`, `eval/examples/reference_case.json`, `eval/scenarios.yaml:19–30` | Successfully retrieves Table 10 Note (ii)(b) (height cap on road $<9\text{ m}$) and Table 9 setbacks; routes to `revise-and-recheck`. |

---

## 4. LLMOps Requirements (L1 – L6)

| Req ID | Requirement | Status | Primary Implementation | Tests & Verification | Operational Notes |
|:---:|:---|:---:|:---|:---|:---|
| **L1** | Chunking, Indexing & Re-Embedding | **VERIFIED** | `src/bpc/retriever/chunking.py`, `src/bpc/retriever/ingest.py`, `store.py` | `tests/test_chunking.py`, `ingest.py --reembed` | Structure-aware chunking preserving tables and footnote clauses; single-document re-embedding. |
| **L2** | Prompt Versioning & Comparison | **VERIFIED** | `prompts/*.yaml`, `src/bpc/common/prompts.py`, `docs/l2_prompt_comparison.md` | `eval/results/real_v1_part2.json` vs `real_v2_part2.json` | Content-hashed prompt tags (`prompt@v2#sha8`); empirical v1 vs v2 comparison on Slice 2. |
| **L3** | Fixed Evaluation Set & Deliberate Change | **VERIFIED** | `eval/scenarios.yaml`, `src/bpc/evaluation/run_eval.py`, `docs/l3_modifier_analysis.md` | `eval/results/compare_real_v2_vs_real_nomod.md` | 22 fixed scenarios ($\ge 20$); 4 explicit metric formulas; modifier on vs off comparison ($n=4$ and $n=11$). |
| **L4** | Guardrails (Injection, Toxicity, Output) | **PARTIAL** | `src/bpc/common/guardrails.py`, `src/bpc/api/main.py:207–213` | `tests/test_guardrails_breaker.py::test_injection_detected` | Architectural wiring verified (withholding notes, output rewrites). Limitation: relies on regex heuristics. |
| **L5** | Token & Cost Accounting | **VERIFIED** | `src/bpc/gateway/main.py:276–295`, `src/bpc/api/main.py:365–401` | `/v1/admin/cost-report`, OpenTelemetry spans | Tokens and costs recorded by agent and step at call time; projected cost per 100 runs. |
| **L6** | Feedback API & Online Evaluation | **VERIFIED** | `src/bpc/api/main.py:321–340`, `src/bpc/agents/worker.py:238–255` | `/v1/runs/{id}/feedback`, `/v1/quality`, Postgres tables | Feedback stored in Postgres; online eval samples live runs (`quality_scores`) and exports metrics. |

---

## 5. Platform and Deployment Requirements (D1 – D8)

| Req ID | Requirement | Status | Primary Implementation | Tests & Verification | Operational Notes |
|:---:|:---|:---:|:---|:---|:---|
| **D1** | Published Data Contracts | **VERIFIED** | `contracts/*.schema.json`, `docs/data_contract.md`, `src/bpc/common/contracts.py` | `scripts/export_contracts.py`, `tests/test_contracts.py` | Strict Pydantic models; exported schemas in exact sync; served via API. |
| **D2** | Idempotent Corpus Pipeline | **VERIFIED** | `src/bpc/retriever/ingest.py`, `corpus/manifest.yaml` | `python -m bpc.retriever.ingest` | Idempotent (0 chunks changed on rerun); freshness and throughput metrics instrumented. |
| **D3** | Compose Stack & Services ($\ge 4$) | **VERIFIED** | `docker-compose.yml`, `docker/Dockerfile.*` | `docker compose config` passes | 16 services; non-root user enforcement; healthchecks on core DAG. |
| **D4** | Secrets & Provider Configuration | **VERIFIED** | `docker-compose.yml:secrets-init`, `.env.example`, `config.py` | Zero committed keys in git; git grep checks | Random passwords generated at first start; `.env` git-ignored; generic model placeholders. |
| **D5** | Tracing, Metrics & Run Reconstruction | **VERIFIED** | `src/bpc/common/observability.py`, `api/main.py:trace`, Grafana dashboard | `GET /v1/runs/{id}/trace`, Prometheus config | OpenTelemetry tracing across HTTP & Redis queues; 32-panel Grafana dashboard; full run replay. |
| **D6** | Predeclared p95 SLO & Locust Benchmark | **VERIFIED** | `docs/slo.md`, `loadtest/locustfile.py`, `docs/loadtest.md` | `loadtest/results/*.csv` | Predeclared p95 $\le 45$ s; end-to-end submit-to-result load testing; concurrency bottleneck identified. |
| **D7** | Caching & Rate Limiting | **VERIFIED** | `src/bpc/api/main.py`, `src/bpc/gateway/main.py`, Redis & Postgres | `docs/loadtest.md`, `tests/test_guardrails_breaker.py` | 4 cache tiers (whole-run, LLM, retrieval, embedding); per-client sliding window rate limiting. |
| **D8** | Runbook & Incident Log | **VERIFIED** | `docs/runbook.md`, `docs/incident_log.md` | Rehearsal log in runbook | Two primary failure modes documented with recovery commands; 8 authentic incident post-mortems. |

---

## 6. Ten Required Demonstration Items (Section 2.7 Brief)

| # | Required Demonstration Item | Status | Verification Command / Click Path | Evidence Captured |
|:---:|:---|:---:|:---|:---|
| **1** | Clean-clone `docker compose up` | **BLOCKED (ENV)** | `docker compose config` (valid); execution blocked by Windows host Docker daemon. | Docker Compose configuration validated without errors. |
| **2** | Valid request produces routed cited recommendation | **VERIFIED** | `python -m bpc.evaluation.smoke valid` / unit test suite | Route, findings, and citations resolve directly to retrieved text. |
| **3** | End-to-end run trace reconstruction | **VERIFIED** | `GET /v1/runs/{id}/trace` | Full trace output with tool calls, queries, passages, prompt versions, and step latencies. |
| **4** | Malformed request quarantined (no agent run) | **VERIFIED** | `tests/test_contracts.py`, `smoke.py::check_malformed` | HTTP 422 returned; logged to `quarantine` table; 0 runs enqueued. |
| **5** | Out-of-corpus case escalates safely | **VERIFIED** | `smoke.py::check_outside`, Scenario S14 | Routes to `specialist-review` with reason stating out-of-corpus jurisdiction. |
| **6** | Verification catches unsupported answer & retries | **VERIFIED** | `tests/test_verify_router.py::test_unresolved_citation_and_fabricated_quote_fail` | Verifier catches unresolved citations/quotes; withholds findings; escalates. |
| **7** | Prompt-injection attempt and guardrail response | **VERIFIED** | `tests/test_guardrails_breaker.py::test_injection_detected`, Scenario S15 | Prompt injection flagged; notes withheld; routes to `specialist-review`. |
| **8** | Circuit breaker opens during outage & degrades | **VERIFIED** | `tests/test_guardrails_breaker.py::test_breaker_opens_and_half_opens` | Breaker trips after threshold; invokes fallback retrieval; routes to specialist. |
| **9** | Locust results against SLO & effect of `--scale` | **VERIFIED** | `loadtest/results/base_1x.md` vs `loadtest/results/scaled_3x.md` | p95 latency at 16 users dropped from 75s to 30s under 3x worker scaling. |
| **10**| Section 4.1 difficult reference case | **VERIFIED** | `eval/examples/reference_case.json`, `docs/reference_case.md` | Table 10 Note (ii)(b) and Table 9 both retrieved and cited; routes `revise-and-recheck`. |
