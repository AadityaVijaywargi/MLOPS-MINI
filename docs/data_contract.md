# Data contracts (D1 / F1)

Every external interface has a published, versioned contract. The machine-readable
JSON Schemas live in `contracts/` (generated from the pydantic models in
`src/bpc/common/contracts.py` by `scripts/export_contracts.py`) and are served live at
`GET /v1/contracts/{proposal|run_result|feedback|reject}`; the OpenAPI document at
`/docs` embeds the proposal schema as the request body of `POST /v1/proposals`.

Contract version: **1.0** (`schema_version` field; breaking changes bump it).

## Interfaces

| Interface | Direction | Contract |
|---|---|---|
| `POST /v1/proposals` | in | `proposal.schema.json` -> 202 `submit_response.schema.json`, 422 `reject_response.schema.json`, 429 |
| `GET /v1/runs/{id}` | out | `{run_id, status, ..., result: run_result.schema.json}` |
| `GET /v1/runs/{id}/trace` | out | run reconstruction (events, per-step latency/cost, verification) |
| `POST /v1/runs/{id}/feedback` | in | `feedback.schema.json` |
| retriever `/v1/search`, `/v1/clause/{id}`, `/v1/references` | internal | pydantic models in `retriever/main.py` |
| llm-gateway `/v1/chat` | internal | `ChatIn` in `gateway/main.py`; provider side is the OpenAI chat-completions format |

## Proposal: validation at the ingestion boundary

Validation runs in the API process **before a run row exists or anything is queued**.
A rejected request is written to the `quarantine` table with its raw body and field-level
errors, counted in `ingest_rejected_total{reason}`, and answered with 422 and
`agent_run_started: false`.

| Layer | Rules |
|---|---|
| Schema | JSON object; unknown fields forbidden (`extra=forbid`); required fields present |
| Type | numbers / integers / booleans / strings as declared |
| Range | `plot.area_sqm` (10, 200000]; widths 1.5-1000 m; road 1-120 m; height 2-300 m; floors 1-100; FAR (0, 20]; coverage (0, 100]; setbacks 0-200 m; notes <= 2000 chars; `client_reference` `^[A-Za-z0-9._-]{1,64}$` |
| Category | `jurisdiction` in {BBMP-Bengaluru}; `zone`, `building_use`, `plot.ring`, `options.prompt_variant` enums |
| Cross-field | area ~ width x depth (10%) unless `is_irregular`; front+rear < depth; left+right < width; footprint (area x coverage) fits inside the setback envelope; FAR <= floors x coverage; height plausible for floor count; built-up area ~ FAR x area (5%); dwelling units consistent with use; secondary road only for corner plots |
| Content | toxicity in `notes` -> rejected (`toxic_content`); suspected prompt injection -> **accepted but notes withheld** from every model and the run is routed to specialist review |
| Size | body <= 64 KB |

Example rejection:
```json
{"error": "validation_failed", "quarantine_id": 7, "agent_run_started": false,
 "errors": [
   {"loc": "zone", "msg": "Input should be 'residential_main', 'residential_mixed', ...", "type": "enum"},
   {"loc": "plot.area_sqm", "msg": "area 500.0 differs from width x depth (108.0) by more than 10%; ...", "type": "cross_field"}]}
```

## Result

`route` is one of `clear-for-submission | revise-and-recheck | specialist-review`, always
with `reason`. Every `finding` carries `citations[]` with `chunk_id`, `clause_label`, `page`,
the verbatim `quote` and the full `passage_text` it was verified against. `escalation`
lists why a human is needed. `prompt_versions` records the exact prompt artifacts used,
`cost_usd` and `tokens` the model spend. `disclaimer` states that the service does not certify.
