# Runbook

The two most likely failure modes in production, judged by where the system
depends on something it does not control: the model provider (free tiers have
low rate limits and occasional outages) and the run pipeline backing up (the
queue between the API and the agents).

---

## 1. Model provider unavailable or rate-limited

**Symptom**
- Runs come back as `specialist-review` with reason starting "Model provider unavailable"
  and `degraded: true`; the web client shows "Retrieved provisions for the reviewer"
  but no findings.
- Grafana > *LLM provider*: `llm_circuit_state` = 2 (open); "Provider calls by outcome"
  shows `failed`; "degraded" line rising. `llm_retries_total` climbing before that.
- Gateway logs: `"provider retry"` then `"provider failed" ... circuit: open`.

**Confirm**
```bash
curl -s localhost:8000/health
docker compose exec llm-gateway python -c "import urllib.request;print(urllib.request.urlopen('http://localhost:8002/admin/circuit').read().decode())"
docker compose logs --since 10m llm-gateway | grep -E "provider (retry|failed)"
```
- `HTTP 429` in the error -> rate limit / quota. `timeout` or `transport error` -> outage
  or network. `HTTP 401/403` -> key revoked or wrong (this is *not* retried and will not
  open the circuit; runs fail at the first model call instead).

**Recover**
1. Rate limit: lower load first - reduce `RATE_LIMIT_PER_MINUTE`, reduce
   `WORKER_CONCURRENCY`, then `docker compose up -d llm-gateway researcher assessor`.
   Responses are cached at temperature 0, so retries of identical proposals cost nothing.
2. Outage: configure the fallback provider (`LLM_FALLBACK_*` in `.env`) and restart the
   gateway; the gateway fails over automatically while the primary circuit is open.
3. Key problem: fix `LLM_PRIMARY_API_KEY` in `.env`, `docker compose up -d llm-gateway`.
4. When the provider is back the circuit half-opens after `CIRCUIT_COOLDOWN_S` and closes
   on the first success; to force it: `POST /admin/circuit/reset` on the gateway.
5. Re-submit degraded runs (they are never cached): find them with
   `SELECT run_id FROM runs WHERE degraded ORDER BY created_at DESC;`

---

## 2. Runs stuck / queue backing up

**Symptom**
- Runs stay `queued` or `researching`; the client keeps polling; eventually they come
  back `failed` with "Run exceeded its 300 s deadline" (the API reaper).
- Grafana: `queue_depth{state="waiting"}` growing; "Run end-to-end latency p95" above
  the 45 s SLO line; `agent_inflight_runs` flat at `WORKER_CONCURRENCY x replicas`.

**Confirm**
```bash
docker compose ps                      # are researcher/assessor healthy? restarting?
docker compose logs --since 10m researcher assessor | grep -E "error|failed"
docker compose exec redis redis-cli LLEN q:research
docker compose exec redis redis-cli LLEN q:research:processing
```
- Workers down/crash-looping -> processing list holds jobs with expired leases.
- Workers up but saturated -> waiting list grows while in-flight is at the cap.
- Retriever slow -> `retrieval_search_seconds` p95 high; `retriever` CPU at its limit.

**Recover**
1. Workers crashed: `docker compose up -d researcher assessor`. Jobs whose lease expired
   are re-queued automatically by the reaper (attempt + 1); after `JOB_MAX_ATTEMPTS` the
   run is failed and escalated rather than answered.
2. Saturated: scale out - `docker compose up -d --scale researcher=3 --scale assessor=3`
   (see `docs/loadtest.md` for what scaling does and does not fix).
3. Retriever is the bottleneck: it embeds queries on CPU in one process; raise its CPU
   share or run a second replica behind the service name (stateless, reads the index
   volume), and keep `RETRIEVAL_CACHE_ENABLED=true`.
4. Redis full (`OOM command not allowed`): `noeviction` is deliberate so jobs are never
   silently dropped - clear stale cache keys `redis-cli --scan --pattern 'llm:*' | xargs redis-cli del`
   and raise `--maxmemory`.

---

## Other quick checks

| Check | Command |
|---|---|
| Whole stack health | `docker compose ps` |
| Reconstruct a run | `curl -s localhost:8000/v1/runs/<run_id>/trace` |
| Rejected submissions | `curl -s localhost:8000/v1/quarantine` |
| Index freshness | Grafana "Index age / chunks", or `docker compose exec retriever python -c "import json;print(json.load(open('/index/meta.json'))['built_at'])"` |
| Re-index after a corpus change | `docker compose run --rm indexer && docker compose exec retriever python -c "import urllib.request;urllib.request.urlopen(urllib.request.Request('http://localhost:8001/admin/reload',method='POST'))"` |

---

## 3. Operational Rehearsal Log: Scenario 1 (Provider Outage & Circuit Breaker)

**Rehearsal Operator:** Friend 3 (Aarav Yuval B G, SRN: PES1UG24AM004)
**Date:** 2026-10-20
**Target Failure Mode:** §1 Model provider unavailable or rate-limited

### Step-by-Step Execution:

1. **Baseline State Verification:**
   - Gateway health checked via `GET http://llm-gateway:8002/admin/circuit`.
   - Initial state: `state: 'closed'`, `consecutive_failures: 0`, `fault: 'none'`.
2. **Fault Injection:**
   - Injected primary provider failure via `POST http://llm-gateway:8002/admin/fault` with payload `{"mode": "down"}`.
   - Gateway acknowledged fault mode update to `"down"`.
3. **Trigger & Resilience Mechanism:**
   - Submitted unique proposal `run_cbbaa291da5d41b4`.
   - Observed gateway retry sequence with exponential backoff:
     - Attempt 1: backoff delay 2.04 s (`error: "fault injection: provider down"`)
     - Attempt 2: backoff delay 8.40 s
     - Attempt 3: backoff delay 14.74 s
     - Attempt 4: backoff delay 31.49 s
   - Upon the 5th failure (`CIRCUIT_FAILURE_THRESHOLD=5`), the circuit breaker transitioned to `state: 'open'`.
4. **Graceful Degradation Verification:**
   - Run `run_cbbaa291da5d41b4` completed with status `escalated` and route `specialist-review`.
   - Reason emitted: `"Model provider unavailable (circuit open / outage): candidate provisions were retrieved but no finding was made. Degraded mode - a person must assess."`
   - Verified that `degraded: true` was set, findings were safely withheld (`findings: []`) to prevent false certifications, and 8 candidate retrieved provisions were preserved for human review.
5. **System Recovery & Circuit Reset:**
   - Cleared fault via `POST /admin/fault` (`{"mode": "none"}`).
   - Reset circuit via `POST /admin/circuit/reset`.
   - Gateway confirmed transition: `[{"state": "open"}, {"state": "closed"}]` with `consecutive_failures: 0`.
   - Submitted unique verification proposal `run_fe5771ae1e484efa` to test end-to-end recovery against the live Gemini provider.
   - Polled until terminal state was reached:
     - **Status:** `completed`
     - **Route:** `clear-for-submission`
     - **Degraded flag:** `false`
     - **Findings:** 7 verified findings recorded across all mandatory topics (setbacks, height, FAR, ground coverage, parking).
     - **Reason:** `"Every mandatory topic has a verified finding and no provision is violated. Clear for submission, subject to professional review."`
     - **Observed Resilience:** During the assessment phase, the gateway seamlessly absorbed and retried an intermittent upstream `HTTP 503 ("model experiencing high demand")`, and the assessor executed a standard verification retry, successfully reaching full compliance resolution without human intervention.
