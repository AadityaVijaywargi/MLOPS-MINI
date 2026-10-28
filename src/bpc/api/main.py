"""Public API (F1/A4/D1). Submission is asynchronous: POST returns a run id at
once (202) and the caller polls GET /v1/runs/{id}. Polling rather than callbacks
because the main caller is a browser / office tool behind NAT that cannot
receive a webhook, polling needs no outbound calls from us (no SSRF surface,
no retry bookkeeping for unreachable callers), and a 2 s poll is negligible
next to a 10-60 s run. A Redis queue sits between submission and execution.

The ingestion boundary validates schema, types, ranges, categories and
cross-field consistency *before* a run exists; rejects are quarantined with
field-level errors and never reach a queue or an agent."""
from __future__ import annotations

from contextlib import asynccontextmanager

import asyncio
import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, JSONResponse
from prometheus_client import Counter, Gauge

from ..common.config import get_settings
from ..common.contracts import (
    TERMINAL_STATUSES, Escalation, FeedbackIn, FieldError, Proposal, RejectResponse, Route, RunResult,
    SubmitResponse, validate_proposal,
)
from ..common.db import create_pool, get_run, migrate, record_event, update_run
from ..common.guardrails import screen_text
from ..common.observability import (
    correlation_id_var, current_trace_id, get_logger, inject_trace_context, install_http_middleware,
    mark_service_started, setup_logging, setup_tracing,
)
from ..common.prompts import assessor_variant
from ..common.queue import JobQueue

SERVICE = "api"
setup_logging(SERVICE)
log = get_logger(SERVICE)
settings = get_settings()
MAX_BODY = 64 * 1024

RUNS_SUBMITTED = Counter("runs_submitted_total", "Accepted proposals", ["cached"])
INGEST_REJECTED = Counter("ingest_rejected_total", "Proposals rejected at the ingestion boundary", ["reason"])
RATE_LIMITED = Counter("rate_limited_total", "Requests rejected by the per-client rate limit")
GUARDRAIL_INPUT = Counter("guardrail_input_total", "Input guardrail outcomes", ["flag"])
QUEUE_DEPTH = Gauge("queue_depth", "Jobs waiting / in flight", ["queue", "state"])
RUNS_BY_STATUS = Gauge("runs_by_status", "Runs in the last hour by status", ["status"])
RUNS_REAPED = Counter("runs_reaped_total", "Runs failed by the deadline reaper")
FEEDBACK = Counter("feedback_total", "Feedback received", ["satisfactory"])

@asynccontextmanager
async def _lifespan(_app):
    await _startup()
    yield


app = FastAPI(
    lifespan=_lifespan,
    title="Building Plan Compliance Pre-Check Service",
    version="1.0",
    description="Pre-checks a building proposal against the BBMP Building Bye-laws 2003 and the BDA RMP-2015 "
                "Zoning Regulations. Produces cited findings and a route; it never certifies compliance.",
)
install_http_middleware(app, SERVICE)
setup_tracing(SERVICE, app)
STATIC = Path(__file__).parent / "static"


class State:
    pool = None
    redis: aioredis.Redis | None = None
    http: httpx.AsyncClient | None = None
    q_research: JobQueue | None = None
    q_assess: JobQueue | None = None
    index_meta: dict = {}
    index_meta_at: float = 0.0


S = State()


async def _startup() -> None:
    mark_service_started(SERVICE)
    S.pool = await create_pool()
    await migrate(S.pool)
    S.redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    S.http = httpx.AsyncClient()
    S.q_research = JobQueue(S.redis, "research", settings.job_lease_s)
    S.q_assess = JobQueue(S.redis, "assess", settings.job_lease_s)
    asyncio.create_task(_housekeeping())


async def _housekeeping() -> None:
    """Deadline reaper + gauges. A run past RUN_DEADLINE_S is failed and escalated:
    an incomplete run is never returned as a confident answer."""
    while True:
        try:
            rows = await S.pool.fetch(
                "SELECT run_id FROM runs WHERE status NOT IN ('completed','escalated','failed') "
                "AND created_at < now() - make_interval(secs => $1)", settings.run_deadline_s)
            for r in rows:
                result = RunResult(
                    run_id=r["run_id"], status="failed", route=Route.specialist,
                    reason=f"Run exceeded its {int(settings.run_deadline_s)} s deadline and did not complete. "
                           "No finding is given; refer for human review.",
                    escalation=Escalation(required=True, reasons=["run_deadline_exceeded"]),
                    flags=["run_incomplete"])
                await update_run(S.pool, r["run_id"], status="failed", route=Route.specialist.value,
                                 reason=result.reason, result=result.model_dump(mode="json"), finished_at=_now())
                await record_event(S.pool, r["run_id"], "api", "reaper", "deadline", status="failed")
                RUNS_REAPED.inc()
            for name, q in (("research", S.q_research), ("assess", S.q_assess)):
                waiting, inflight = await q.depth()
                QUEUE_DEPTH.labels(name, "waiting").set(waiting)
                QUEUE_DEPTH.labels(name, "inflight").set(inflight)
            for row in await S.pool.fetch(
                    "SELECT status, count(*) AS n FROM runs WHERE created_at > now() - interval '1 hour' GROUP BY status"):
                RUNS_BY_STATUS.labels(row["status"]).set(row["n"])
        except Exception as exc:
            log.error("housekeeping failed", error=str(exc))
        await asyncio.sleep(10)


def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


def _client_id(request: Request) -> str:
    cid = request.headers.get("X-Client-Id", "")
    if cid and len(cid) <= 64 and all(c.isalnum() or c in "._-" for c in cid):
        host = request.client.host if request.client else "unknown"
        # Protect internal high-rate override roles (e.g. loadtest, eval) from remote client spoofing
        if cid in ("loadtest", "eval") and host not in ("127.0.0.1", "localhost", "::1", "testclient"):
            return f"{cid}:{host}"
        return cid
    return f"ip:{request.client.host if request.client else 'unknown'}"


_LOCAL_RL: dict[tuple[str, int], int] = {}
_LOCAL_RL_LAST_PRUNE: float = 0.0


def _check_local_rate_limit(client_id: str, limit: int) -> int | None:
    """Bounded in-memory fallback rate limiter used when Redis is unavailable or unconfigured.
    Prunes expired windows to prevent unbounded memory growth."""
    global _LOCAL_RL_LAST_PRUNE
    now = time.time()
    window = int(now // 60)
    if now - _LOCAL_RL_LAST_PRUNE > 60:
        cutoff = window - 2
        for k in [k for k in _LOCAL_RL if k[1] < cutoff]:
            _LOCAL_RL.pop(k, None)
        _LOCAL_RL_LAST_PRUNE = now

    key = (client_id, window)
    count = _LOCAL_RL.get(key, 0) + 1
    _LOCAL_RL[key] = count
    if count > limit:
        RATE_LIMITED.inc()
        return 60 - int(now % 60)
    return None


async def _rate_limited(client_id: str) -> int | None:
    """Fixed one-minute window per client. Enforces rate limits via Redis when available,
    falling back to a bounded in-memory sliding window on Redis connection error to
    preserve model budget protection."""
    limit = settings.rate_limit_for(client_id)
    if S.redis is None:
        return _check_local_rate_limit(client_id, limit)
    try:
        window = int(time.time() // 60)
        key = f"rl:{client_id}:{window}"
        count = await S.redis.incr(key)
        if count == 1:
            await S.redis.expire(key, 70)
        if count > limit:
            RATE_LIMITED.inc()
            return 60 - int(time.time() % 60)
        return None
    except Exception as exc:
        log.warning("redis rate limit check failed, falling back to local rate limiter", error=str(exc))
        return _check_local_rate_limit(client_id, limit)


async def _quarantine(client_id: str, reason: str, raw: str, errors: list[FieldError]) -> JSONResponse:
    qid = await S.pool.fetchval(
        "INSERT INTO quarantine (client_id, correlation_id, reason, raw_body, errors) VALUES ($1,$2,$3,$4,$5) RETURNING id",
        client_id, correlation_id_var.get(), reason, raw[:MAX_BODY], [e.model_dump(mode="json") for e in errors])
    INGEST_REJECTED.labels(reason).inc()
    log.warning("proposal quarantined", reason=reason, quarantine_id=qid, errors=len(errors))
    body = RejectResponse(quarantine_id=qid, errors=errors)
    return JSONResponse(status_code=422, content=body.model_dump(mode="json"))


async def _index_meta() -> dict:
    if time.time() - S.index_meta_at > 60:
        try:
            r = await S.http.get(f"{settings.retriever_url}/v1/meta", timeout=3)
            S.index_meta, S.index_meta_at = r.json(), time.time()
        except Exception:
            pass
    return S.index_meta


def _proposal_schema_openapi() -> dict:
    return {"requestBody": {"required": True, "content": {"application/json": {
        "schema": {"$ref": "#/components/schemas/Proposal"}}}}}


@app.post("/v1/proposals", status_code=202, response_model=SubmitResponse, openapi_extra=_proposal_schema_openapi(),
          responses={422: {"model": RejectResponse}, 429: {"description": "rate limited"}},
          summary="Submit a building proposal for pre-check (async)")
async def submit(request: Request):
    client_id = _client_id(request)
    wait = await _rate_limited(client_id)
    if wait is not None:
        return JSONResponse(status_code=429, headers={"Retry-After": str(wait)},
                            content={"error": "rate_limited", "retry_after_s": wait,
                                     "limit_per_minute": settings.rate_limit_for(client_id)})
    raw = await request.body()
    text = raw.decode("utf-8", errors="replace")
    if len(raw) > MAX_BODY:
        return await _quarantine(client_id, "body_too_large", text[:2000],
                                 [FieldError(loc="$", msg=f"body exceeds {MAX_BODY} bytes", type="size")])
    try:
        data = json.loads(raw or b"null")
    except json.JSONDecodeError as exc:
        return await _quarantine(client_id, "malformed_json", text,
                                 [FieldError(loc="$", msg=f"invalid JSON: {exc.msg} at pos {exc.pos}", type="json")])
    proposal, errors = validate_proposal(data)
    if errors or proposal is None:
        reason = "cross_field" if errors and all(e.type == "cross_field" for e in errors) else "schema"
        return await _quarantine(client_id, reason, text, errors)
    screen = screen_text(proposal.notes)
    if screen.toxic:
        GUARDRAIL_INPUT.labels("toxic").inc()
        return await _quarantine(client_id, "toxic_content", text, [FieldError(
            loc="notes", msg="notes contain abusive or threatening language", type="toxicity",
            input=", ".join(screen.toxic_matches))])
    flags = screen.flags()
    for f in flags:
        GUARDRAIL_INPUT.labels(f).inc()

    meta = await _index_meta()
    variant = assessor_variant(proposal.options.prompt_variant)
    phash = proposal.canonical_hash()
    cache_key = hashlib.sha256(json.dumps([phash, meta.get("index_version"), variant, settings.modifier_search_enabled,
                                           sorted(flags)]).encode()).hexdigest()
    run_id = "run_" + uuid.uuid4().hex[:16]
    trace_id = current_trace_id()
    proposal_json = proposal.model_dump(mode="json")
    cached = None
    if settings.run_cache_enabled and not proposal.options.bypass_cache:
        cached = await S.pool.fetchrow(
            "SELECT run_id, status, route, reason, result, category, dossier, prompt_versions FROM runs "
            "WHERE cache_key=$1 AND status IN ('completed','escalated') AND NOT degraded "
            "AND finished_at > now() - make_interval(secs => $2) ORDER BY finished_at DESC LIMIT 1",
            cache_key, settings.run_cache_ttl_s)
    if cached:
        result = dict(cached["result"]) | {"run_id": run_id, "cost_usd": 0.0}
        await S.pool.execute(
            """INSERT INTO runs (run_id, client_id, correlation_id, proposal_hash, cache_key, proposal, status, route,
                   reason, category, result, dossier, flags, prompt_versions, trace_id, cached_from, finished_at)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16, now())""",
            run_id, client_id, correlation_id_var.get() or run_id, phash, cache_key, proposal_json, cached["status"],
            cached["route"], cached["reason"], cached["category"], result, cached["dossier"], flags,
            cached["prompt_versions"], trace_id, cached["run_id"])
        await record_event(S.pool, run_id, "api", "ingest", "cache_hit", payload={"cached_from": cached["run_id"]})
        RUNS_SUBMITTED.labels("true").inc()
        return JSONResponse(status_code=200, content=_submit_body(run_id, cached["status"], cached["run_id"]))

    await S.pool.execute(
        """INSERT INTO runs (run_id, client_id, correlation_id, proposal_hash, cache_key, proposal, status, flags,
               trace_id) VALUES ($1,$2,$3,$4,$5,$6,'queued',$7,$8)""",
        run_id, client_id, correlation_id_var.get() or run_id, phash, cache_key, proposal_json, flags, trace_id)
    await record_event(S.pool, run_id, "api", "ingest", "accepted", payload={
        "client_id": client_id, "flags": flags, "injection_score": screen.injection_score,
        "injection_matches": screen.injection_matches, "variant": variant,
        "index_version": meta.get("index_version")})
    await S.q_research.put({"run_id": run_id, "trace": inject_trace_context()})
    RUNS_SUBMITTED.labels("false").inc()
    log.info("run accepted", run_id=run_id, flags=flags)
    return JSONResponse(status_code=202, content=_submit_body(run_id, "queued", None))


def _submit_body(run_id: str, status: str, cached_from: str | None) -> dict:
    return SubmitResponse(run_id=run_id, status=status, status_url=f"/v1/runs/{run_id}",
                          trace_url=f"/v1/runs/{run_id}/trace", cached_from=cached_from).model_dump(mode="json")


@app.get("/v1/runs/{run_id}", summary="Poll run status / result")
async def get_status(run_id: str):
    run = await get_run(S.pool, run_id)
    if not run:
        raise HTTPException(404, "unknown run id")
    done = run["status"] in TERMINAL_STATUSES
    body: dict[str, Any] = {"run_id": run_id, "status": run["status"], "created_at": run["created_at"].isoformat(),
                            "finished_at": run["finished_at"].isoformat() if run["finished_at"] else None,
                            "cached_from": run["cached_from"]}
    if done:
        body["result"] = run["result"]
    else:
        body["poll_after_s"] = 2.0
    return body


@app.get("/v1/runs/{run_id}/trace", summary="Reconstruct a run: every tool call, query, passage, prompt "
         "version, per-step latency and cost, and the verification outcome")
async def get_trace(run_id: str):
    run = await get_run(S.pool, run_id)
    if not run:
        raise HTTPException(404, "unknown run id")
    events = [dict(e) for e in await S.pool.fetch("SELECT * FROM run_events WHERE run_id=$1 ORDER BY id", run_id)]
    for e in events:
        e["ts"] = e["ts"].isoformat()
    steps: dict[str, dict] = {}
    for e in events:
        key = f"{e['agent']}.{e['step']}"
        s = steps.setdefault(key, {"events": 0, "latency_ms": 0.0, "cost_usd": 0.0, "prompt_tokens": 0,
                                   "completion_tokens": 0})
        s["events"] += 1
        s["latency_ms"] += e["latency_ms"] or 0
        s["cost_usd"] += e["cost_usd"] or 0
        s["prompt_tokens"] += e["prompt_tokens"] or 0
        s["completion_tokens"] += e["completion_tokens"] or 0
    dossier = run["dossier"] or {}
    return {
        "run_id": run_id, "status": run["status"], "route": run["route"], "reason": run["reason"],
        "client_id": run["client_id"], "correlation_id": run["correlation_id"],
        "created_at": run["created_at"].isoformat(),
        "finished_at": run["finished_at"].isoformat() if run["finished_at"] else None,
        "jaeger_url": f"{settings.jaeger_ui_url}/trace/{run['trace_id']}" if run["trace_id"] else None,
        "prompt_versions": run["prompt_versions"],
        "proposal": run["proposal"], "flags": run["flags"], "cached_from": run["cached_from"],
        "per_step": steps,
        "totals": {"latency_ms": round(sum(s["latency_ms"] for s in steps.values()), 1),
                   "cost_usd": round(sum(s["cost_usd"] for s in steps.values()), 8),
                   "llm_calls": sum(1 for e in events if e["kind"] == "llm_call"),
                   "tool_calls": sum(1 for e in events if e["kind"] == "tool_call")},
        "queries": dossier.get("queries", []),
        "passages_retrieved": dossier.get("all_retrieved_ids", []),
        "binding_provisions": [{k: b[k] for k in ("chunk_id", "clause_label", "topics", "why")} for b in dossier.get("binding", [])],
        "verification": [e["payload"] | {"status": e["status"]} for e in events if e["kind"] == "verification"],
        "events": events,
    }


@app.post("/v1/runs/{run_id}/feedback", status_code=201, summary="Mark a result satisfactory or not, with a reason")
async def feedback(run_id: str, body: FeedbackIn, request: Request):
    run = await get_run(S.pool, run_id)
    if not run:
        raise HTTPException(404, "unknown run id")
    screen = screen_text(body.reason)
    if screen.toxic:
        raise HTTPException(422, "feedback reason contains abusive language")
    fid = await S.pool.fetchval(
        "INSERT INTO feedback (run_id, client_id, satisfactory, reason) VALUES ($1,$2,$3,$4) RETURNING id",
        run_id, _client_id(request), body.satisfactory, body.reason)
    FEEDBACK.labels(str(body.satisfactory).lower()).inc()
    return {"feedback_id": fid, "run_id": run_id}


@app.get("/v1/feedback/summary")
async def feedback_summary():
    rows = await S.pool.fetch(
        """SELECT r.route, f.satisfactory, count(*) AS n FROM feedback f JOIN runs r USING (run_id)
           GROUP BY r.route, f.satisfactory ORDER BY r.route""")
    total = sum(r["n"] for r in rows)
    sat = sum(r["n"] for r in rows if r["satisfactory"])
    recent = await S.pool.fetch(
        "SELECT run_id, satisfactory, reason, created_at FROM feedback ORDER BY id DESC LIMIT 20")
    return {"total": total, "satisfactory_rate": (sat / total) if total else None,
            "by_route": [dict(r) for r in rows],
            "recent": [dict(r) | {"created_at": r["created_at"].isoformat()} for r in recent]}


@app.get("/v1/quality", summary="Online quality scores of sampled live runs over time")
async def quality(hours: int = 24):
    rows = await S.pool.fetch(
        """SELECT date_trunc('hour', scored_at) AS hour, source, count(*) AS n, avg(groundedness) AS groundedness,
                  avg(context_relevance) AS context_relevance, avg(faithfulness) AS faithfulness,
                  avg(hallucination_rate) AS hallucination_rate
           FROM quality_scores WHERE scored_at > now() - make_interval(hours => $1)
           GROUP BY 1, 2 ORDER BY 1""", hours)
    return {"series": [dict(r) | {"hour": r["hour"].isoformat()} for r in rows]}


@app.get("/v1/quarantine", summary="Recently quarantined (rejected) submissions")
async def quarantine(limit: int = 20):
    rows = await S.pool.fetch("SELECT id, received_at, client_id, correlation_id, reason, errors FROM quarantine "
                              "ORDER BY id DESC LIMIT $1", min(limit, 200))
    return {"items": [dict(r) | {"received_at": r["received_at"].isoformat()} for r in rows]}


@app.get("/v1/admin/cost-report", summary="Cost per 100 runs and the largest single cost driver")
async def cost_report(hours: int = 24, price_in_per_mtok: float | None = None, price_out_per_mtok: float | None = None):
    rows = await S.pool.fetch(
        """SELECT e.agent, e.step, count(*) AS calls, sum(e.prompt_tokens) AS pt, sum(e.completion_tokens) AS ct,
                  sum(e.cost_usd) AS cost
           FROM run_events e JOIN runs r USING (run_id)
           WHERE e.kind='llm_call' AND r.finished_at IS NOT NULL AND r.cached_from IS NULL
             AND r.created_at > now() - make_interval(hours => $1)
           GROUP BY 1, 2 ORDER BY cost DESC NULLS LAST, pt DESC""", hours)
    n_runs = await S.pool.fetchval(
        "SELECT count(*) FROM runs WHERE finished_at IS NOT NULL AND cached_from IS NULL "
        "AND created_at > now() - make_interval(hours => $1)", hours) or 0
    n_cached = await S.pool.fetchval(
        "SELECT count(*) FROM runs WHERE cached_from IS NOT NULL AND created_at > now() - make_interval(hours => $1)",
        hours) or 0
    drivers = []
    for r in rows:
        d = {"agent": r["agent"], "step": r["step"], "calls": r["calls"], "prompt_tokens": r["pt"] or 0,
             "completion_tokens": r["ct"] or 0, "cost_usd": float(r["cost"] or 0)}
        if price_in_per_mtok is not None and price_out_per_mtok is not None:
            d["projected_cost_usd"] = d["prompt_tokens"] * price_in_per_mtok / 1e6 + d["completion_tokens"] * price_out_per_mtok / 1e6
        drivers.append(d)
    total = sum(d["cost_usd"] for d in drivers)
    key = "projected_cost_usd" if drivers and "projected_cost_usd" in drivers[0] else "cost_usd"
    projected_total = sum(d.get(key, 0) for d in drivers)
    tokens = sum(d["prompt_tokens"] + d["completion_tokens"] for d in drivers)
    largest = max(drivers, key=lambda d: (d.get(key, 0), d["prompt_tokens"] + d["completion_tokens"]), default=None)
    return {
        "window_hours": hours, "runs": n_runs, "cache_hits": n_cached,
        "cost_usd_recorded_total": round(total, 6),
        "cost_per_100_runs_usd": round(projected_total / n_runs * 100, 6) if n_runs else None,
        "cost_basis": key,
        "tokens_per_run": round(tokens / n_runs, 1) if n_runs else None,
        "largest_cost_driver": largest,
        "by_step": drivers,
    }


@app.get("/v1/contracts", summary="Published data contracts")
async def contracts():
    return {"contracts": {"proposal": "/v1/contracts/proposal", "run_result": "/v1/contracts/run_result",
                          "feedback": "/v1/contracts/feedback", "reject": "/v1/contracts/reject"}}


@app.get("/v1/contracts/{name}")
async def contract(name: str):
    models = {"proposal": Proposal, "run_result": RunResult, "feedback": FeedbackIn, "reject": RejectResponse}
    if name not in models:
        raise HTTPException(404, "unknown contract")
    return models[name].model_json_schema()


@app.get("/health")
async def health():
    checks = {}
    try:
        await S.pool.fetchval("SELECT 1")
        checks["postgres"] = "ok"
    except Exception as exc:
        checks["postgres"] = f"error: {exc}"
    try:
        await S.redis.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"
    ok = all(v == "ok" for v in checks.values())
    return JSONResponse(status_code=200 if ok else 503, content={"status": "ok" if ok else "degraded", **checks})


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(STATIC / "index.html")


def custom_openapi() -> dict:
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version, description=app.description, routes=app.routes)
    comps = schema.setdefault("components", {}).setdefault("schemas", {})
    prop = Proposal.model_json_schema(ref_template="#/components/schemas/{model}")
    comps.update(prop.pop("$defs", {}))
    comps["Proposal"] = prop
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi  # type: ignore[method-assign]
