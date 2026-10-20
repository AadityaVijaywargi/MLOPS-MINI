"""LLM gateway: the only component that talks to a model provider.

The model sits behind an interface we control, so the provider is changed by
configuration only (any OpenAI-compatible endpoint: a hosted free tier, Ollama,
or the in-repo stub). Responsibilities:
  * per-call timeout, bounded retry with exponential backoff + jitter (A5)
  * a circuit breaker per provider and a primary -> fallback -> 503 path (A5)
  * token and cost accounting at the time of the call, labelled per agent/step (L5)
  * response cache for deterministic (temperature 0) calls (D7)
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import asyncio
import re
from collections import deque
import hashlib
import json
import os
import random
import time
from dataclasses import dataclass
from typing import Any

import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Gauge, Histogram
from pydantic import BaseModel, Field

from ..common.config import get_settings
from ..common.observability import (
    get_logger, install_http_middleware, mark_service_started, setup_logging, setup_tracing, tracer,
)
from .breaker import STATE_VALUE, CircuitBreaker

SERVICE = "llm-gateway"
setup_logging(SERVICE)
log = get_logger(SERVICE)
settings = get_settings()

LLM_REQUESTS = Counter("llm_requests_total", "Provider calls", ["provider", "outcome"])
LLM_LATENCY = Histogram("llm_call_seconds", "Provider call latency", ["provider"],
                        buckets=(0.1, 0.25, 0.5, 1, 2, 4, 8, 15, 30, 60))
LLM_TOKENS = Counter("llm_tokens_total", "Tokens", ["provider", "kind", "agent", "step"])
LLM_COST = Counter("llm_cost_usd_total", "Cost in USD at time of call", ["provider", "agent", "step"])
LLM_RETRIES = Counter("llm_retries_total", "Retries against a provider", ["provider", "reason"])
LLM_CACHE = Counter("llm_cache_total", "LLM response cache", ["result"])
LLM_DEGRADED = Counter("llm_unavailable_total", "Requests that exhausted every provider", ["agent"])
CIRCUIT_STATE = Gauge("llm_circuit_state", "0=closed 1=half-open 2=open", ["provider"])


@dataclass
class Provider:
    name: str
    base_url: str
    api_key: str | None
    model: str
    price_in: float  # USD per 1M prompt tokens
    price_out: float  # USD per 1M completion tokens
    timeout_s: float
    json_mode: bool
    breaker: CircuitBreaker
    limiter: "RateLimiter"
    extra_body: dict
    fault: str = "none"  # fault injection: none | down | slow


class RateLimiter:
    """Sliding one-minute window. Keeps us under a provider's requests-per-minute quota
    (free tiers) by making callers wait for a slot instead of collecting 429s."""

    def __init__(self, rpm: int):
        self.rpm = rpm
        self.times: deque[float] = deque()
        self.lock = asyncio.Lock()

    async def acquire(self) -> float:
        if self.rpm <= 0:
            return 0.0
        waited = 0.0
        async with self.lock:
            while True:
                now = time.monotonic()
                while self.times and now - self.times[0] >= 60:
                    self.times.popleft()
                if len(self.times) < self.rpm:
                    self.times.append(now)
                    return waited
                delay = 60 - (now - self.times[0]) + 0.05
                await asyncio.sleep(delay)
                waited += delay


def _provider(prefix: str, name: str) -> Provider | None:
    env = os.environ
    base = env.get(f"{prefix}_BASE_URL", "").strip()
    model = env.get(f"{prefix}_MODEL", "").strip()
    if not base or not model:
        return None
    return Provider(
        name=name,
        base_url=base.rstrip("/"),
        api_key=env.get(f"{prefix}_API_KEY") or None,
        model=model,
        price_in=float(env.get(f"{prefix}_PRICE_IN_PER_MTOK", "0") or 0),
        price_out=float(env.get(f"{prefix}_PRICE_OUT_PER_MTOK", "0") or 0),
        timeout_s=float(env.get(f"{prefix}_TIMEOUT_S", "30") or 30),
        json_mode=env.get(f"{prefix}_JSON_MODE", "false").lower() == "true",
        breaker=CircuitBreaker(
            name,
            failure_threshold=int(env.get("CIRCUIT_FAILURE_THRESHOLD", "3")),
            cooldown_s=float(env.get("CIRCUIT_COOLDOWN_S", "30")),
        ),
        limiter=RateLimiter(int(env.get(f"{prefix}_MAX_RPM", "0") or 0)),
        extra_body=json.loads(env.get(f"{prefix}_EXTRA_BODY", "") or "{}"),
    )


PROVIDERS: list[Provider] = [p for p in (_provider("LLM_PRIMARY", "primary"), _provider("LLM_FALLBACK", "fallback")) if p]
MAX_RETRIES = int(os.environ.get("LLM_MAX_RETRIES", "2"))
BACKOFF_BASE_S = float(os.environ.get("LLM_BACKOFF_BASE_S", "0.5"))
CACHE_ENABLED = os.environ.get("LLM_CACHE_ENABLED", "true").lower() == "true"
CACHE_TTL_S = int(os.environ.get("LLM_CACHE_TTL_S", "86400"))
FAULT_INJECTION = os.environ.get("ENABLE_FAULT_INJECTION", "false").lower() == "true"
QUOTA_MAX_WAIT_S = float(os.environ.get("LLM_QUOTA_MAX_WAIT_S", "90"))
LLM_QUOTA_WAIT = Counter("llm_quota_wait_seconds_total", "Seconds spent waiting on provider quota", ["provider", "kind"])

@asynccontextmanager
async def _lifespan(_app):
    await _startup()
    yield


app = FastAPI(title="BPC LLM gateway", version="1.0", lifespan=_lifespan)
install_http_middleware(app, SERVICE)
setup_tracing(SERVICE, app)
_client: httpx.AsyncClient | None = None
_redis: aioredis.Redis | None = None


class ChatMeta(BaseModel):
    run_id: str = "adhoc"
    agent: str = "unknown"
    step: str = "unknown"
    prompt_version: str | None = None
    no_cache: bool = False


class ChatIn(BaseModel):
    messages: list[dict[str, Any]] = Field(..., min_length=1)
    tools: list[dict[str, Any]] | None = None
    tool_choice: Any = None
    temperature: float = 0.0
    max_tokens: int = Field(1200, ge=16, le=8192)
    json_mode: bool = False
    meta: ChatMeta = Field(default_factory=ChatMeta)


class Retryable(Exception):
    pass


class QuotaExceeded(Exception):
    """HTTP 429: the provider is healthy but we are over quota. Not an outage."""

    def __init__(self, msg: str, retry_after_s: float | None):
        super().__init__(msg)
        self.retry_after_s = retry_after_s


def _retry_after(resp: httpx.Response) -> float | None:
    header = resp.headers.get("retry-after")
    if header and header.replace(".", "", 1).isdigit():
        return float(header)
    m = re.search(r'retryDelay"?\s*:\s*"?(\d+(?:\.\d+)?)s', resp.text)
    return float(m.group(1)) if m else None


async def _startup() -> None:
    global _client, _redis
    mark_service_started(SERVICE)
    _client = httpx.AsyncClient()
    _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    for p in PROVIDERS:
        CIRCUIT_STATE.labels(p.name).set(0)
    log.info("providers configured", providers=[{"name": p.name, "host": httpx.URL(p.base_url).host} for p in PROVIDERS])


def _cache_key(body: ChatIn) -> str:
    payload = {"m": body.messages, "t": body.tools, "tc": body.tool_choice, "mt": body.max_tokens,
               "j": body.json_mode, "p": [(p.name, p.model) for p in PROVIDERS]}
    return "llm:" + hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


async def _call_once(p: Provider, body: ChatIn) -> dict:
    if p.fault == "down":
        raise Retryable("fault injection: provider down")
    if p.fault == "slow":
        await asyncio.sleep(p.timeout_s + 1)
    payload: dict[str, Any] = {
        "model": p.model, "messages": body.messages, "temperature": body.temperature, "max_tokens": body.max_tokens,
        **p.extra_body,
    }
    if body.tools:
        payload["tools"] = body.tools
        if body.tool_choice is not None:
            payload["tool_choice"] = body.tool_choice
    if body.json_mode and p.json_mode and not body.tools:
        payload["response_format"] = {"type": "json_object"}
    headers = {"Content-Type": "application/json"}
    if p.api_key:
        headers["Authorization"] = f"Bearer {p.api_key}"
    try:
        resp = await asyncio.wait_for(
            _client.post(f"{p.base_url}/chat/completions", json=payload, headers=headers, timeout=p.timeout_s),
            timeout=p.timeout_s + 2,
        )
    except (httpx.TimeoutException, asyncio.TimeoutError) as exc:
        raise Retryable(f"timeout after {p.timeout_s}s") from exc
    except httpx.TransportError as exc:
        raise Retryable(f"transport error: {exc}") from exc
    if resp.status_code == 429:
        raise QuotaExceeded(f"HTTP 429: {resp.text[:200]}", _retry_after(resp))
    if resp.status_code >= 500:
        raise Retryable(f"HTTP {resp.status_code}: {resp.text[:200]}")
    if resp.status_code >= 400:
        raise HTTPException(502, f"provider rejected request: HTTP {resp.status_code}: {resp.text[:300]}")
    try:
        data = resp.json()
    except ValueError:
        # e.g. a misconfigured base URL that serves a web page instead of the API
        raise HTTPException(502, f"provider returned non-JSON from {resp.url} (check LLM_*_BASE_URL): "
                                 f"{resp.text[:120]!r}") from None
    if not isinstance(data, dict) or "choices" not in data:
        raise HTTPException(502, f"provider response has no 'choices' (check LLM_*_BASE_URL): {str(data)[:200]}")
    return data


async def _call_with_retry(p: Provider, body: ChatIn) -> tuple[dict, int]:
    """Every failed attempt is a real provider failure and counts towards the breaker;
    once the breaker opens we stop retrying instead of hammering a dead provider."""
    attempt = 0
    quota_waited = 0.0
    while True:
        LLM_QUOTA_WAIT.labels(p.name, "pacing").inc(await p.limiter.acquire())
        try:
            return await _call_once(p, body), attempt
        except QuotaExceeded as exc:
            delay = exc.retry_after_s or min(10.0 * (2 ** min(attempt, 3)), 40.0)
            if quota_waited + delay > QUOTA_MAX_WAIT_S:
                p.breaker.failure()  # quota will not recover in time for this request
                CIRCUIT_STATE.labels(p.name).set(STATE_VALUE[p.breaker.state])
                raise Retryable(f"quota exhausted after waiting {quota_waited:.0f}s: {exc}") from exc
            LLM_RETRIES.labels(p.name, "quota").inc()
            LLM_QUOTA_WAIT.labels(p.name, "429").inc(delay)
            log.warning("provider quota, waiting", provider=p.name, delay_s=round(delay, 1),
                        waited_s=round(quota_waited, 1))
            await asyncio.sleep(delay)
            quota_waited += delay
            attempt += 1
        except Retryable as exc:
            p.breaker.failure()
            CIRCUIT_STATE.labels(p.name).set(STATE_VALUE[p.breaker.state])
            if attempt >= MAX_RETRIES or p.breaker.state == "open":
                raise
            delay = BACKOFF_BASE_S * (2 ** attempt) * (0.5 + random.random())
            LLM_RETRIES.labels(p.name, str(exc).split(":")[0][:40]).inc()
            log.warning("provider retry", provider=p.name, attempt=attempt + 1, delay_s=round(delay, 2), error=str(exc))
            await asyncio.sleep(delay)
            attempt += 1


def _usage(data: dict, body: ChatIn) -> tuple[int, int, bool]:
    usage = data.get("usage") or {}
    pt, ct = usage.get("prompt_tokens"), usage.get("completion_tokens")
    total = usage.get("total_tokens")
    if pt is not None and ct is not None and total and total > pt + ct:
        ct = total - pt  # hidden "thinking" tokens are billed as output (e.g. Gemini)
    if pt is None or ct is None:  # estimate (~4 chars/token) when the provider omits usage
        pt = sum(len(json.dumps(m)) for m in body.messages) // 4
        msg = (data.get("choices") or [{}])[0].get("message", {})
        ct = len(json.dumps(msg)) // 4
        return int(pt), int(ct), True
    return int(pt), int(ct), False


@app.post("/v1/chat")
async def chat(body: ChatIn):
    meta = body.meta
    use_cache = CACHE_ENABLED and body.temperature == 0 and not meta.no_cache and _redis is not None
    if use_cache:
        try:
            hit = await _redis.get(_cache_key(body))
        except Exception:
            hit = None
        if hit:
            LLM_CACHE.labels("hit").inc()
            out = json.loads(hit)
            out.update(cached=True, cost_usd=0.0, latency_ms=0.0, attempts=0)
            return out
        LLM_CACHE.labels("miss").inc()
    errors: list[str] = []
    for p in PROVIDERS:
        if not p.breaker.allow():
            errors.append(f"{p.name}: circuit open")
            CIRCUIT_STATE.labels(p.name).set(STATE_VALUE[p.breaker.state])
            continue
        start = time.perf_counter()
        with tracer().start_as_current_span("llm.call") as span:
            span.set_attribute("llm.provider", p.name)
            span.set_attribute("llm.agent", meta.agent)
            span.set_attribute("llm.step", meta.step)
            span.set_attribute("run.id", meta.run_id)
            try:
                data, retries = await _call_with_retry(p, body)
            except Retryable as exc:
                LLM_REQUESTS.labels(p.name, "failed").inc()
                errors.append(f"{p.name}: {exc}")
                log.error("provider failed", provider=p.name, error=str(exc), circuit=p.breaker.state)
                continue
            elapsed = time.perf_counter() - start
            p.breaker.success()
            CIRCUIT_STATE.labels(p.name).set(0)
            LLM_REQUESTS.labels(p.name, "ok").inc()
            LLM_LATENCY.labels(p.name).observe(elapsed)
            pt, ct, estimated = _usage(data, body)
            cost = pt * p.price_in / 1e6 + ct * p.price_out / 1e6
            LLM_TOKENS.labels(p.name, "prompt", meta.agent, meta.step).inc(pt)
            LLM_TOKENS.labels(p.name, "completion", meta.agent, meta.step).inc(ct)
            LLM_COST.labels(p.name, meta.agent, meta.step).inc(cost)
            span.set_attribute("llm.prompt_tokens", pt)
            span.set_attribute("llm.completion_tokens", ct)
            span.set_attribute("llm.cost_usd", cost)
            message = (data.get("choices") or [{}])[0].get("message", {}) or {}
            out = {
                "message": {"role": "assistant", "content": message.get("content"),
                            "tool_calls": message.get("tool_calls") or None},
                "provider": p.name, "model": p.model,
                "usage": {"prompt_tokens": pt, "completion_tokens": ct, "estimated": estimated},
                "cost_usd": round(cost, 8), "latency_ms": round(elapsed * 1000, 1),
                "attempts": retries + 1, "fallback_used": p.name != PROVIDERS[0].name, "cached": False,
            }
            if use_cache:
                try:
                    await _redis.set(_cache_key(body), json.dumps(out), ex=CACHE_TTL_S)
                except Exception:
                    pass
            return out
    LLM_DEGRADED.labels(meta.agent).inc()
    return JSONResponse(status_code=503, content={"error": "llm_unavailable", "detail": errors})


@app.get("/health")
async def health():
    return {"status": "ok", "providers": [p.breaker.snapshot() | {"fault": p.fault} for p in PROVIDERS]}


@app.get("/admin/circuit")
async def circuit():
    return {"providers": [p.breaker.snapshot() | {"fault": p.fault} for p in PROVIDERS]}


@app.post("/admin/circuit/reset")
async def circuit_reset():
    for p in PROVIDERS:
        p.breaker.reset()
        CIRCUIT_STATE.labels(p.name).set(0)
    return await circuit()


class FaultIn(BaseModel):
    provider: str = "primary"
    mode: str = Field("down", pattern="^(none|down|slow)$")


@app.post("/admin/fault")
async def fault(body: FaultIn):
    """Demo/test hook (disabled unless ENABLE_FAULT_INJECTION=true)."""
    if not FAULT_INJECTION:
        raise HTTPException(403, "fault injection disabled")
    for p in PROVIDERS:
        if p.name == body.provider or body.provider == "all":
            p.fault = body.mode
    return await circuit()
