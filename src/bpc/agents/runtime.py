"""Shared agent runtime: model calls through the gateway, retriever calls with
timeouts + bounded retry, per-step event recording (the run reconstruction log)
and the per-agent Prometheus metrics (A6)."""
from __future__ import annotations

import asyncio
import json
import random
import re
import time
from dataclasses import dataclass, field
from typing import Any

import asyncpg
import httpx
from prometheus_client import Counter, Gauge, Histogram

from ..common.config import get_settings
from ..common.db import record_event
from ..common.observability import get_logger, outgoing_headers, tracer
from ..common.prompts import Prompt

log = get_logger("agents")
settings = get_settings()

AGENT_TASKS = Counter("agent_tasks_total", "Agent tasks by outcome", ["agent", "outcome"])
AGENT_STEPS = Histogram("agent_steps_per_run", "Reasoning steps (model turns) per run", ["agent"],
                        buckets=(1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 30))
AGENT_TOOL_CALLS = Histogram("agent_tool_calls_per_run", "Tool calls per run", ["agent"],
                             buckets=(0, 1, 2, 4, 6, 8, 10, 12, 16, 20, 25, 30))
AGENT_STEP_SECONDS = Histogram("agent_step_seconds", "Latency per step", ["agent", "step"],
                               buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 4, 8, 15, 30, 60))
AGENT_RUN_SECONDS = Histogram("agent_run_seconds", "Agent latency per run", ["agent"],
                              buckets=(0.5, 1, 2, 5, 10, 15, 20, 30, 45, 60, 90, 120, 180))
AGENT_RETRIES = Counter("agent_retries_total", "Retries by kind", ["agent", "kind"])
AGENT_INFLIGHT = Gauge("agent_inflight_runs", "Runs being processed", ["agent"])
RUN_E2E = Histogram("run_end_to_end_seconds", "Submission to final result", ["route"],
                    buckets=(1, 2, 5, 10, 15, 20, 30, 45, 60, 90, 120, 180, 300))
RUN_COST = Histogram("run_cost_usd", "LLM cost per completed run", buckets=(0, 1e-5, 1e-4, 5e-4, 1e-3, 5e-3, 0.01, 0.05))
ONLINE_QUALITY = Gauge("online_quality_score", "Latest online-scored quality metric (sampled runs)", ["metric"])
ONLINE_QUALITY_HIST = Histogram("online_quality", "Online-scored quality metric distribution", ["metric"],
                                buckets=(0, 0.25, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0))


class LLMUnavailable(Exception):
    """The gateway could not get an answer from any provider (circuit open / outage)."""


class ToolFailure(Exception):
    pass


@dataclass
class RunContext:
    run_id: str
    agent: str
    pool: asyncpg.Pool
    http: httpx.AsyncClient
    deadline: float
    steps: int = 0
    tool_calls: int = 0
    llm_calls: int = 0
    prompt_versions: dict[str, str] = field(default_factory=dict)
    no_cache: bool = False

    def remaining(self) -> float:
        return self.deadline - time.monotonic()

    async def event(self, step: str, kind: str, **kw: Any) -> None:
        try:
            await record_event(self.pool, self.run_id, self.agent, step, kind, **kw)
        except Exception as exc:  # never let audit logging kill a run
            log.error("event write failed", error=str(exc))


def _truncate(obj: Any, limit: int = 4000) -> Any:
    s = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, default=str)
    return s if len(s) <= limit else s[:limit] + f"...[+{len(s) - limit} chars]"


async def llm_chat(
    ctx: RunContext,
    step: str,
    prompt: Prompt,
    messages: list[dict],
    tools: list[dict] | None = None,
    json_mode: bool = False,
    max_tokens: int = 1500,
) -> dict:
    ctx.prompt_versions[prompt.prompt_id] = prompt.tag
    timeout = max(5.0, min(settings.llm_client_timeout_s, ctx.remaining()))
    body = {
        "messages": messages, "tools": tools, "temperature": 0.0, "max_tokens": max_tokens, "json_mode": json_mode,
        "meta": {"run_id": ctx.run_id, "agent": ctx.agent, "step": step, "prompt_version": prompt.tag,
                 "no_cache": ctx.no_cache},
    }
    start = time.perf_counter()
    with tracer().start_as_current_span(f"{ctx.agent}.llm.{step}") as span:
        span.set_attribute("run.id", ctx.run_id)
        span.set_attribute("prompt.version", prompt.tag)
        try:
            resp = await ctx.http.post(f"{settings.llm_gateway_url}/v1/chat", json=body, timeout=timeout,
                                       headers=outgoing_headers())
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            elapsed = (time.perf_counter() - start) * 1000
            await ctx.event(step, "llm_call", name=prompt.prompt_id, status="error", latency_ms=elapsed,
                            prompt_version=prompt.tag, payload={"error": f"gateway unreachable/timeout: {exc}"})
            raise LLMUnavailable(f"gateway timeout/unreachable: {exc}") from exc
        elapsed = (time.perf_counter() - start) * 1000
        if resp.status_code != 200:
            await ctx.event(step, "llm_call", name=prompt.prompt_id, status="error", latency_ms=elapsed,
                            prompt_version=prompt.tag, payload={"http_status": resp.status_code, "body": resp.text[:500]})
            raise LLMUnavailable(f"gateway returned {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
    ctx.llm_calls += 1
    AGENT_STEP_SECONDS.labels(ctx.agent, f"llm.{step}").observe(elapsed / 1000)
    if data.get("attempts", 1) > 1:
        AGENT_RETRIES.labels(ctx.agent, "llm_provider").inc(data["attempts"] - 1)
    usage = data.get("usage", {})
    await ctx.event(
        step, "llm_call", name=prompt.prompt_id, latency_ms=elapsed, prompt_version=prompt.tag,
        prompt_tokens=usage.get("prompt_tokens"), completion_tokens=usage.get("completion_tokens"),
        cost_usd=data.get("cost_usd"),
        payload={"provider": data.get("provider"), "model": data.get("model"), "attempts": data.get("attempts"),
                 "cached": data.get("cached"), "fallback_used": data.get("fallback_used"),
                 "request_last_message": _truncate(messages[-1].get("content") or "", 3000),
                 "response": _truncate(data.get("message"), 4000)},
    )
    return data["message"]


def parse_json(text: str | None) -> dict | None:
    if not text:
        return None
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    candidate = text[start:end + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        # Strip trailing commas before closing braces/brackets and retry
        cleaned = re.sub(r",\s*([}\]])", r"\1", candidate)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return None


async def retriever_call(ctx: RunContext, method: str, path: str, payload: dict | None = None) -> dict:
    """Retriever HTTP call with per-call timeout and bounded exponential backoff."""
    url = f"{settings.retriever_url}{path}"
    last: Exception | None = None
    for attempt in range(settings.tool_max_retries + 1):
        timeout = max(1.0, min(settings.tool_timeout_s, ctx.remaining()))
        try:
            if method == "GET":
                resp = await ctx.http.get(url, timeout=timeout, headers=outgoing_headers())
            else:
                resp = await ctx.http.post(url, json=payload, timeout=timeout, headers=outgoing_headers())
            if resp.status_code == 404:
                return {"error": resp.json().get("detail", "not found")}
            if resp.status_code >= 500:
                raise ToolFailure(f"retriever HTTP {resp.status_code}")
            resp.raise_for_status()
            return resp.json()
        except (httpx.TimeoutException, httpx.TransportError, ToolFailure) as exc:
            last = exc
            if attempt < settings.tool_max_retries:
                AGENT_RETRIES.labels(ctx.agent, "tool").inc()
                await asyncio.sleep(0.3 * (2 ** attempt) * (0.5 + random.random()))
    raise ToolFailure(f"retriever unavailable after retries: {last}")
