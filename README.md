# Building Plan Compliance Pre-Check Service

An AgentOps multi-agent service that pre-checks architectural building proposals against the **BBMP Building Bye-laws 2003** and the **BDA Revised Master Plan 2015 Zoning Regulations** (Bengaluru jurisdiction), routing each proposal to **`clear-for-submission`**, **`revise-and-recheck`**, or **`specialist-review`** with clause-level citations resolving directly to retrieved legal text.

> [!IMPORTANT]
> **Non-Negotiable Safety Boundary:** This system is strictly an architectural **pre-check decision-support tool**, not a certifier. It never certifies a building plan or replaces a licensed architect or structural engineer. Its output is an evidentiary finding with cited provisions; human specialists make all legal determinations. Any ambiguity, conflicting provisions, out-of-corpus jurisdiction, or failed verification deterministically escalates to `specialist-review`.

Course: **UE24AM342AA5 — ML System Design & AgentOps** (Mini Project 05, Level 3 Jackfruit)<br>
Domain: **Urban Development and Construction**<br>
Team Members: **Aaditya Vijaywargi (Friend 1)**, **Dilipan Y (Friend 2)**, **Aarav Yuval B G (Friend 3, PES1UG24AM004)**

---

## 1. System Architecture & Workflow

The service employs a decoupled multi-agent architecture with asynchronous job queues, deterministic verification, and strict quarantine isolation:

```
[ Incoming Proposal ]
         │
         ▼
[ FastAPI Gateway ] ──(Invalid / Toxic)──► [ Quarantine Table (HTTP 422) ] (0 agent runs queued)
         │ (Valid HTTP 202)
         ▼
[ Redis Queue: q:research ]
         │
         ▼
[ Researcher Agent (LangGraph) ] ──► [ Hybrid Retriever (FAISS + BM25) ]
         │ (Tool loop: 6 tools, hybrid modifier check)
         ▼
[ Redis Queue: q:assess ]
         │
         ▼
[ Assessor Agent ] ──► [ Deterministic Verifier (AST Math + Verbatim Quote) ]
         │
         ▼
[ Deterministic Router ] ──► [ Final Finding & Route: clear | revise | specialist ]
```

- **Researcher Agent (`src/bpc/agents/researcher.py`):** Uses LangGraph to classify spatial entities and iteratively query the hybrid retriever. Features a **hybrid modifier check step** combining LLM reflection with a deterministic variable-interaction safety net to uncover secondary clauses (such as road-width height caps).
- **Assessor Agent (`src/bpc/agents/assessor.py`):** Extracts required values and derives comparisons from the retrieved legal dossier.
- **Deterministic Verifier (`src/bpc/agents/verify.py`):** Pure Python verification that evaluates arithmetic derivations via AST (`ast.parse`), enforces 10-character verbatim quote checks, and validates status consistency before returning findings.
- **Deterministic Router (`src/bpc/agents/router.py`):** Applies legal precedence rules (BDA ZR2015 supersedes BBMP 2003 on governed parameters) and escalates conflicts, exemptions, or ungrounded claims.

---

## 2. Quickstart & Clean-Clone Startup

### Prerequisites
- Docker Desktop or Docker Engine with Docker Compose v2.24+
- ~6 GB disk space (for CPU PyTorch and embedding models)
- ~4 GB free RAM
- No API keys required (runs with built-in stub by default)

### 1. Launch the 16-Service Stack
```bash
git clone https://github.com/AadityaVijaywargi/MLOPS-MINI.git
cd MLOPS-MINI
docker compose up -d --build
```
*Note:* The first build takes 5–10 minutes to download CPU wheels and embedding weights. The `indexer` service parses the corpus PDFs, builds the FAISS + BM25 index, and terminates cleanly before the `retriever` and agents come up.

### 2. Verify Health
```bash
docker compose ps
```

### 3. Open Endpoints & Interfaces
| Interface | URL | Purpose |
|---|---|---|
| **Web Client** | `http://localhost:8000` | Interactive proposal submission, preset demo cases, and collapsible citations |
| **OpenAPI Contracts** | `http://localhost:8000/docs` | Published data contracts and interactive schema documentation |
| **Grafana Dashboard** | `http://localhost:3000` | 32-panel live observability dashboard (anonymous viewer) |
| **Jaeger Traces** | `http://localhost:16686` | Distributed traces across HTTP calls, Redis queues, and LLM steps |
| **Prometheus Metrics**| `http://localhost:9090` | Raw metrics scraper |

---

## 3. Submitting Proposals & Inspecting Results

### Submit from CLI
```bash
# 1. Submit proposal (returns HTTP 202 with run_id)
curl -s -X POST http://localhost:8000/v1/proposals \
  -H "Content-Type: application/json" \
  -H "X-Client-Id: student" \
  -d @eval/examples/reference_case.json

# 2. Poll status (until completed, escalated, or failed)
curl -s http://localhost:8000/v1/runs/<run_id>

# 3. View end-to-end execution trace (tool calls, prompt versions, AST math, costs)
curl -s http://localhost:8000/v1/runs/<run_id>/trace
```

### Keyless Stub vs Real Model Configuration
- **Default (Keyless Stub Mode):** Without a `.env`, the stack uses the in-repo stub LLM (`src/bpc/stub/main.py`). The stub executes the complete asynchronous pipeline, but never certifies or invents findings, safely routing runs to `specialist-review`.
- **Optional Real Provider Mode:**
  ```bash
  cp .env.example .env
  # Set LLM_PRIMARY_BASE_URL, LLM_PRIMARY_API_KEY, LLM_PRIMARY_MODEL
  docker compose up -d
  ```
  Any OpenAI-compatible chat completions endpoint with tool calling is supported.

---

## 4. Section 4.1 Difficult Reference Case

- **Scenario:** Residential building on a small plot (108 m²) abutting a narrow road (6.0 m) proposing Stilt + GF + 3 floors (height 12.5 m, FAR 2.0, front setback 1.0 m).
- **The Challenge:** Standard keyword searches for "residential setbacks" return Table 8 and Table 10, but omit the road-width height restriction.
- **The Solution:** The research agent's hybrid modifier step detects the road-width dependency and issues derived query `"maximum height of building restricted by road width"`, ranking **Table 10 Note (ii)(b)** (p. 28) #1.
- **The Outcome:**
  - Table 10 Note (ii)(b) caps height at 11.5 m on roads $<9.0\text{ m}$ -> **VIOLATED** (12.5 m proposed).
  - Table 9 mandates 5.0 m setbacks for buildings $>11.5\text{ m}$ -> **VIOLATED** (1.0 m proposed).
  - Front setback 1.0 m $\ge 1.0\text{ m}$ for plots $\le 120\text{ m}^2$ -> **SATISFIED**.
  - Final deterministic route: **`revise-and-recheck`** (100% violation recall, 0 errors).

---

## 5. Verification, Testing & Evaluation Commands

### Local Automated Test Suite (No Docker Required)
```powershell
$env:PYTHONPATH="src"
.\.venv\Scripts\pytest -v
```
**Result:** **35 passed in < 5 seconds** (+10 regression and robustness tests for rate-limit fallbacks, quote thresholds, comparison operators, and JSON parser string masking).

### Contract & Whitespace Checks
```powershell
# Verify JSON Schemas are in exact sync with Pydantic models
python scripts/export_contracts.py --check

# Verify zero trailing whitespace or line-ending defects
git diff --check
```

### Full Stack Smoke Test (Requires Docker)
```bash
docker compose exec api python -m bpc.evaluation.smoke
```

### Evaluation Benchmark
```bash
# Run evaluation on the 22-scenario test set
docker compose --profile tools run --rm eval python -m bpc.evaluation.run_eval --label baseline
```

---

## 6. Demonstration Hooks (Web Client & CLI)

| Demo | How |
|---|---|
| Malformed request quarantined, no run started | web client scenario "Malformed request", then `GET /v1/quarantine`; `runs` count unchanged |
| Prompt injection | web client scenario "Prompt injection" (the Validate stage turns amber with the guardrail flag) |
| Outside corpus -> escalation | web client scenario "Outside the corpus" |
| Self-verification catches an unsupported answer | `docker compose exec llm-stub python -c "import urllib.request,json;urllib.request.urlopen(urllib.request.Request('http://localhost:8003/admin/mode',data=json.dumps({'mode':'hallucinate_once'}).encode(),headers={'Content-Type':'application/json'}))"` then submit with "Force a fresh run" ticked; the Self-verification panel shows `failed` then a retry |
| Circuit breaker + degradation | `docker compose stop llm-stub` (or `POST /admin/fault` on the gateway), submit; Grafana circuit state goes to open, run returns degraded `specialist-review` with candidate provisions |

---

## 7. Project Documentation Directory

| Document | Description |
|---|---|
| [`docs/report.md`](docs/report.md) | Comprehensive final technical report covering architecture, evaluations, and load tests |
| [`docs/audit/FINAL_AUDIT.md`](docs/audit/FINAL_AUDIT.md) | Reconciled requirement compliance scorecard and tested-vs-historical audit verdict |
| [`docs/audit/PRESENTATION_READINESS.md`](docs/audit/PRESENTATION_READINESS.md) | 8–12 minute live demonstration script with exact click paths, payloads, and fallbacks |
| [`docs/audit/VIVA_NOTES.md`](docs/audit/VIVA_NOTES.md) | Master viva preparation guide answering 13 core technical and architectural questions |
| [`docs/audit/REQUIREMENTS_TRACEABILITY.md`](docs/audit/REQUIREMENTS_TRACEABILITY.md) | Itemized matrix tracing all F, A, L, D requirements to code and test evidence |
| [`docs/audit/FINDINGS.md`](docs/audit/FINDINGS.md) | Register of 11 audit findings, confirmed fixes, and disproven false positives |
| [`docs/audit/CHANGELOG.md`](docs/audit/CHANGELOG.md) | Itemized log of all code, test, and documentation modifications |
| [`docs/slo.md`](docs/slo.md) | Predeclared p95 latency SLO specification ($\le 45\text{ s}$ at up to 1 run/s) |
| [`docs/loadtest.md`](docs/loadtest.md) | Locust load testing benchmark results and 3x worker scaling analysis |
| [`docs/incident_log.md`](docs/incident_log.md) | 8 authentic engineering post-mortems documenting failures and architectural pivots |

---

## 8. Honest Status & Verification Disclosure

- **Locally Unit-Tested & Verified:** 35 unit and regression tests pass cleanly on Python 3.12, verifying contracts, quarantine boundaries, circuit breakers, rate limiter in-memory fallback, and deterministic AST verification.
- **Historical Evidence Available:** 22-scenario evaluation results (Slices 1–3), prompt comparisons (v1 vs v2), modifier ablation analysis, and Locust benchmark CSVs are fully preserved in `eval/results/` and `loadtest/results/`.
- **Environment-Blocked Limitation:** Live clean-clone container orchestration (`docker compose up`) could not be executed on the current Windows audit machine because the host Windows Docker Desktop service (`com.docker.service`) was stopped and requires elevated administrator privileges to launch. `docker compose config` was validated with 16 services syntax-clean.
