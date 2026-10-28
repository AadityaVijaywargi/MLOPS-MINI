# Cleanup Manifest

**Audit Branch:** `audit/mini-project-05-requirement-alignment`  
**Protocol:** Section 6 Safe Cleanup Protocol  
**Principle:** Evidence-backed keep/consolidate/archive/remove decisions. No arbitrary deletions. Preserve all evaluation evidence, experiment logs, load test metrics, and corpus provenance.

---

## File Disposition Inventory

| Path | Type | Role & Provenance | References Checked | Candidate Rationale | Decision | Evidence & Canonical Location |
|:---|:---:|:---|:---|:---|:---:|:---|
| `corpus/raw/*.pdf` | PDF | Authentic municipal regulations (BBMP 2003, BDA RMP-2015). | `corpus/manifest.yaml`, `src/bpc/retriever/ingest.py` | Must be preserved for corpus verification. | **KEEP** | Checked-in legal corpus source of truth. |
| `contracts/*.schema.json` | JSON | Published external REST interface contracts. | `docs/data_contract.md`, `src/bpc/api/main.py`, `scripts/export_contracts.py` | Required by D1 / F1 published API contract. | **KEEP** | Canonical JSON Schemas generated from Pydantic. |
| `eval/results/*.json`, `*.md` | JSON / MD | Team evaluation results, prompt comparisons, and modifier ablation runs. | `docs/report.md`, `docs/l2_prompt_comparison.md`, `docs/l3_modifier_analysis.md` | Contains empirical proof of student evaluations. | **KEEP** | Primary evaluation provenance for Evaluations 1 & 2. |
| `eval/results/dev/*` | JSON / MD | Iterative development trial logs (trial_31lite, etc.). | Git history, `docs/incident_log.md` (INC-005 to INC-008) | Documents development lineage and lessons learned. | **KEEP** | Development history and incident reproduction evidence. |
| `loadtest/results/*` | CSV / MD | Benchmark metrics across baseline, 3x scaled, and Friend 3 verification runs. | `docs/loadtest.md`, `docs/slo.md`, `docs/report.md` | Empirical proof of Locust load testing and scaling behavior. | **KEEP** | Historical load test proof required by D6 / A7. |
| `prompts/*.yaml` | YAML | Versioned system and agent prompt definitions. | `src/bpc/common/prompts.py`, `src/bpc/agents/` | Versioned artifacts with SHA8 content hashes (L2). | **KEEP** | Canonical versioned prompt registry. |
| `scripts/export_contracts.py` | Python | Contract generation and sync validation script. | `contracts/*.schema.json`, `docs/data_contract.md` | Developer tooling to maintain contract sync. | **KEEP** | Essential tooling for schema export. |
| `scripts/team_eval.sh`, `team_eval.ps1` | Shell | Automated multi-worker evaluation orchestration scripts. | `docs/team_eval.md` | Reproducible evaluation pipeline scripts. | **KEEP** | Scripted replication of evaluation slices. |
| `scripts/loadtest.py` | Python | Stepped concurrency automation for Locust benchmarks. | `docs/loadtest.md` | Automation script for reproducible load testing. | **KEEP** | Load test runner. |
| `scripts/gen_dashboard.py` | Python | Grafana dashboard JSON generator. | `observability/grafana/dashboards/bpc.json` | Tooling to regenerate 32-panel dashboard. | **KEEP** | Dashboard generator. |
| `.env.example` | Config | Documented environment variable template. | `docker-compose.yml`, `src/bpc/common/config.py` | Required by D4 configuration specification. | **KEEP** | Canonical configuration specification. |
| `docker-compose.yml` | YAML | 16-service orchestration definition. | All Dockerfiles, services, and runbooks. | Core requirement D3. | **KEEP** | Compose service topology definition. |

---

## Summary of Decisions
- **Total Files Evaluated:** 225
- **Files Kept:** 225
- **Files Removed:** 0
- **Files Archived:** 0
- **Justification:** Every artifact in the repository serves an active role in runtime execution, automated testing, API contract publication, evaluation provenance, or load-testing traceability. Arbitrary removal of raw evaluation JSONs or load test CSVs would destroy critical empirical evidence required for course assessment.
