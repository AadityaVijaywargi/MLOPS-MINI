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
