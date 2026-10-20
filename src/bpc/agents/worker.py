"""Agent worker process: `python -m bpc.agents.worker researcher|assessor`.

Each role is its own container (A2): the researcher consumes q:research and
hands a persisted dossier to q:assess; the assessor consumes q:assess and may
hand back to q:research once. Failure handling:
  * exception in a run    -> requeued with attempt+1, up to JOB_MAX_ATTEMPTS
  * worker dies mid-run   -> its lease expires; any worker's reaper requeues it
  * attempts exhausted    -> run marked failed + specialist-review, never a
                             confident answer
  * run deadline exceeded -> the API reaper marks it failed the same way
"""
from __future__ import annotations

import asyncio
import os
import random
import socket
import sys
import time
import uuid
from typing import Any

import httpx
import redis.asyncio as aioredis
import structlog
from prometheus_client import start_http_server

from ..common.config import get_settings
from ..common.contracts import TERMINAL_STATUSES, Escalation, Route, RunResult
from ..common.db import create_pool, get_run, migrate, run_cost, update_run
from ..common.observability import (
    attach_trace_context, bind_correlation, detach_trace_context, get_logger, inject_trace_context,
    mark_service_started, setup_logging, setup_tracing, tracer,
)
from ..common.queue import JobQueue
from . import assessor, researcher
from .runtime import (
    AGENT_INFLIGHT, AGENT_RUN_SECONDS, AGENT_STEPS, AGENT_TASKS, AGENT_TOOL_CALLS, ONLINE_QUALITY,
    ONLINE_QUALITY_HIST, RUN_COST, RUN_E2E, RunContext,
)

settings = get_settings()
log = get_logger("worker")


class Worker:
    def __init__(self, role: str):
        self.role = role
        self.worker_id = f"{role}-{socket.gethostname()}-{uuid.uuid4().hex[:6]}"

    async def setup(self) -> None:
        self.pool = await create_pool()
        await migrate(self.pool)
        self.redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        self.http = httpx.AsyncClient(limits=httpx.Limits(max_connections=50))
        self.q_research = JobQueue(self.redis, "research", settings.job_lease_s)
        self.q_assess = JobQueue(self.redis, "assess", settings.job_lease_s)
        self.inbox = self.q_research if self.role == "researcher" else self.q_assess

    # ------------------------------------------------------------ main loop
    async def run_forever(self) -> None:
        await self.setup()
        sem = asyncio.Semaphore(settings.worker_concurrency)
        asyncio.create_task(self.reaper())
        log.info("worker started", worker_id=self.worker_id, concurrency=settings.worker_concurrency)
        while True:
            await sem.acquire()
            try:
                job = await self.inbox.get(timeout_s=2, worker_id=self.worker_id)
            except Exception as exc:
                log.error("queue read failed", error=str(exc))
                sem.release()
                await asyncio.sleep(1)
                continue
            if job is None:
                sem.release()
                continue
            asyncio.create_task(self._guarded(job, sem))

    async def _guarded(self, job: dict, sem: asyncio.Semaphore) -> None:
        beat = asyncio.create_task(self._heartbeat(job))
        AGENT_INFLIGHT.labels(self.role).inc()
        try:
            await self.handle(job)
            await self.inbox.ack(job)
        except Exception as exc:
            log.exception("run failed in worker", run_id=job.get("run_id"), error=str(exc))
            AGENT_TASKS.labels(self.role, "error").inc()
            await self.inbox.ack(job)
            if job.get("attempt", 1) < settings.job_max_attempts:
                retry = {k: v for k, v in job.items() if k != "_raw"} | {"attempt": job.get("attempt", 1) + 1}
                await self.inbox.put(retry)
            else:
                await self.fail_run(job["run_id"], f"{self.role} failed after {job.get('attempt', 1)} attempt(s): {exc}")
        finally:
            beat.cancel()
            AGENT_INFLIGHT.labels(self.role).dec()
            sem.release()

    async def _heartbeat(self, job: dict) -> None:
        while True:
            await asyncio.sleep(settings.job_lease_s / 3)
            try:
                await self.inbox.heartbeat(job)
            except Exception:
                pass

    async def reaper(self) -> None:
        while True:
            await asyncio.sleep(15 + random.random() * 5)
            try:
                for dead in await self.inbox.reap(settings.job_max_attempts):
                    await self.fail_run(dead["run_id"], f"{self.role} worker died mid-run and retries were exhausted")
            except Exception as exc:
                log.error("reaper failed", error=str(exc))

    async def fail_run(self, run_id: str, why: str) -> None:
        run = await get_run(self.pool, run_id)
        if not run or run["status"] in TERMINAL_STATUSES:
            return
        result = RunResult(run_id=run_id, status="failed", route=Route.specialist,
                           reason=f"Run did not complete ({why}). No finding is given; refer for human review.",
                           escalation=Escalation(required=True, reasons=["run_incomplete"]), flags=["run_incomplete"])
        await update_run(self.pool, run_id, status="failed", route=Route.specialist.value, reason=result.reason,
                         result=result.model_dump(mode="json"), finished_at=_now())
        AGENT_TASKS.labels(self.role, "failed").inc()

    # -------------------------------------------------------------- handlers
    async def handle(self, job: dict) -> None:
        run_id = job["run_id"]
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(service=self.role, run_id=run_id, agent=self.role)
        bind_correlation(run_id)
        token = attach_trace_context(job.get("trace"))
        try:
            run = await get_run(self.pool, run_id)
            if not run or run["status"] in TERMINAL_STATUSES:
                log.warning("skipping run", reason="missing or terminal")
                return
            with tracer().start_as_current_span(f"{self.role}.run") as span:
                span.set_attribute("run.id", run_id)
                span.set_attribute("job.attempt", job.get("attempt", 1))
                if self.role == "researcher":
                    await self.research(job, run)
                else:
                    await self.assess(job, run)
        finally:
            detach_trace_context(token)

    def _ctx(self, run: dict, deadline_s: float) -> RunContext:
        opts = run["proposal"].get("options") or {}
        no_cache = bool(opts.get("bypass_cache")) and not opts.get("reuse_model_cache")
        return RunContext(run_id=run["run_id"], agent=self.role, pool=self.pool, http=self.http,
                          deadline=time.monotonic() + deadline_s, no_cache=no_cache)

    async def research(self, job: dict, run: dict) -> None:
        run_id = run["run_id"]
        start = time.perf_counter()
        await update_run(self.pool, run_id, status="researching")
        ctx = self._ctx(run, settings.researcher_deadline_s)
        state: dict[str, Any] = {"proposal": run["proposal"], "notes_withheld": bool(
            {"prompt_injection_suspected", "toxic_content"} & set(run["flags"] or []))}
        if job.get("followup"):
            prev = run["dossier"] or {}
            state.update(followup=job["followup"],
                         passages={p["chunk_id"]: p for p in prev.get("binding", []) + prev.get("other_retrieved", [])},
                         recorded={b["chunk_id"]: {"topics": b["topics"], "why": b.get("why", [])}
                                   for b in prev.get("binding", [])},
                         category=prev.get("category"), classification=prev.get("classification", {}),
                         exemption_signals=prev.get("exemption_signals", []),
                         out_of_scope_signals=prev.get("out_of_scope_signals", []),
                         queries=prev.get("queries", []))
            ctx.prompt_versions.update(prev.get("prompt_versions", {}))
        await ctx.event("run", "agent_start", name="researcher", payload={"attempt": job.get("attempt", 1),
                        "followup": job.get("followup")})
        final = await asyncio.wait_for(
            researcher.GRAPH.ainvoke(state, config={"configurable": {"ctx": ctx}, "recursion_limit": 120}),
            timeout=settings.researcher_deadline_s + 15,
        )
        dossier = researcher.build_dossier(final, ctx)
        if job.get("followup"):
            dossier["handback_round"] = job.get("handbacks", 1)
        await update_run(self.pool, run_id, dossier=dossier, status="assessing", category=dossier.get("category"),
                         degraded=dossier["degraded"])
        elapsed = time.perf_counter() - start
        await ctx.event("run", "handoff", name="researcher->assessor", latency_ms=elapsed * 1000, payload={
            "binding": [b["chunk_id"] for b in dossier["binding"]], "covered": dossier["covered_topics"],
            "missing": dossier["missing_topics"], "degraded": dossier["degraded"], "steps": ctx.steps,
            "tool_calls": ctx.tool_calls, "budget_exhausted": dossier["budget_exhausted"]})
        await self.q_assess.put({"run_id": run_id, "trace": inject_trace_context(),
                                 "handbacks": job.get("handbacks", 0)})
        AGENT_STEPS.labels("researcher").observe(ctx.steps)
        AGENT_TOOL_CALLS.labels("researcher").observe(ctx.tool_calls)
        AGENT_RUN_SECONDS.labels("researcher").observe(elapsed)
        AGENT_TASKS.labels("researcher", "degraded" if dossier["degraded"] else "success").inc()

    async def assess(self, job: dict, run: dict) -> None:
        run_id = run["run_id"]
        start = time.perf_counter()
        ctx = self._ctx(run, settings.assessor_deadline_s)
        variant = assessor.variant_for(run["proposal"])
        state = {"run_id": run_id, "proposal": run["proposal"], "dossier": run["dossier"] or {}, "variant": variant,
                 "flags": run["flags"] or [], "handbacks": job.get("handbacks", 0), "attempts": 0}
        await ctx.event("run", "agent_start", name="assessor", payload={"attempt": job.get("attempt", 1),
                        "variant": variant, "handbacks": job.get("handbacks", 0)})
        final = await asyncio.wait_for(
            assessor.GRAPH.ainvoke(state, config={"configurable": {"ctx": ctx}, "recursion_limit": 40}),
            timeout=settings.assessor_deadline_s + 15,
        )
        elapsed = time.perf_counter() - start
        AGENT_STEPS.labels("assessor").observe(ctx.steps)
        AGENT_TOOL_CALLS.labels("assessor").observe(ctx.tool_calls)
        AGENT_RUN_SECONDS.labels("assessor").observe(elapsed)
        if final.get("handback"):
            await update_run(self.pool, run_id, status="researching")
            await self.q_research.put({"run_id": run_id, "trace": inject_trace_context(),
                                       "followup": final["handback_queries"],
                                       "handbacks": job.get("handbacks", 0) + 1})
            AGENT_TASKS.labels("assessor", "handback").inc()
            return
        result = final["result"]
        cost, pt, ct = await run_cost(self.pool, run_id)
        result["cost_usd"] = round(cost, 8)
        result["tokens"] = {"prompt": pt, "completion": ct}
        pv = result.get("prompt_versions", {})
        await update_run(self.pool, run_id, status=result["status"], route=result["route"], reason=result["reason"],
                         result=result, prompt_versions=pv, flags=result["flags"], finished_at=_now(),
                         degraded=result["degraded"])
        e2e = (_now() - run["created_at"]).total_seconds()
        RUN_E2E.labels(result["route"]).observe(e2e)
        RUN_COST.observe(cost)
        outcome = "degraded" if result["degraded"] else ("escalated" if result["status"] == "escalated" else "success")
        AGENT_TASKS.labels("assessor", outcome).inc()
        log.info("run complete", route=result["route"], e2e_s=round(e2e, 2), cost_usd=cost)
        if final.get("report") and random.random() < settings.online_eval_sample_rate:
            await self.score_online(run_id, final)

    async def score_online(self, run_id: str, final: dict) -> None:
        """L6: score a sample of live runs with the same definitions as the offline eval
        (context relevance online = share of dossier passages used by verified findings)."""
        rep = final["report"]
        dossier = final["dossier"]
        n_ctx = len(dossier.get("binding", [])) + len(dossier.get("other_retrieved", []))
        used = {final["findings"][i]["provision_id"] for i in final.get("ok_idx", [])}
        scores = {"groundedness": rep.get("groundedness"), "faithfulness": rep.get("faithfulness"),
                  "hallucination_rate": rep.get("hallucination_rate"),
                  "context_relevance": (len(used) / n_ctx) if n_ctx else None}
        await self.pool.execute(
            """INSERT INTO quality_scores (run_id, source, groundedness, context_relevance, faithfulness,
                   hallucination_rate, details) VALUES ($1,'online',$2,$3,$4,$5,$6)""",
            run_id, scores["groundedness"], scores["context_relevance"], scores["faithfulness"],
            scores["hallucination_rate"], {"report": rep})
        for k, v in scores.items():
            if v is not None:
                ONLINE_QUALITY.labels(k).set(v)
                ONLINE_QUALITY_HIST.labels(k).observe(v)


def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


def main() -> None:
    role = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("AGENT_ROLE", "")
    if role not in ("researcher", "assessor"):
        raise SystemExit("usage: python -m bpc.agents.worker researcher|assessor")
    setup_logging(role)
    setup_tracing(role)
    mark_service_started(role)
    start_http_server(int(os.environ.get("METRICS_PORT", "9100")))
    asyncio.run(Worker(role).run_forever())


if __name__ == "__main__":
    main()
