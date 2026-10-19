"""Stub LLM provider (D6): an OpenAI-compatible /v1/chat/completions endpoint
that returns fixed, schema-valid responses after a realistic delay, so load
tests measure *our* system rather than a provider's rate limits, and the whole
stack runs end to end with no API key.

It is deliberately dumb: it recognises the task marker in the system prompt
([[task:...]]) and returns a canned response of the right shape. It never
makes a compliance determination (every finding is `not_determinable`), so a
stub-backed run always ends in specialist review."""
from __future__ import annotations

from contextlib import asynccontextmanager

import asyncio
import json
import os
import random
import re
import time
import uuid

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..common.observability import install_http_middleware, mark_service_started, setup_logging

SERVICE = "llm-stub"
setup_logging(SERVICE)
@asynccontextmanager
async def _lifespan(_app):
    await _startup()
    yield


app = FastAPI(title="BPC stub LLM", version="1.0", lifespan=_lifespan)
install_http_middleware(app, SERVICE)

DELAY_MIN = float(os.environ.get("STUB_DELAY_MS_MIN", "800")) / 1000
DELAY_MAX = float(os.environ.get("STUB_DELAY_MS_MAX", "2000")) / 1000
STATE = {"mode": os.environ.get("STUB_MODE", "ok")}  # ok | down | slow | hallucinate | hallucinate_once

DEFAULT_QUERIES = [
    ("setbacks", "setbacks for building by width and depth of site"),
    ("far", "FAR and ground coverage by plot size and road width"),
]


async def _startup() -> None:
    mark_service_started(SERVICE)


def _payload(text: str) -> dict:
    if "PAYLOAD:" in text:
        text = text.split("PAYLOAD:", 1)[1]
    start = text.find("{")
    try:
        return json.loads(text[start:]) if start >= 0 else {}
    except json.JSONDecodeError:
        return {}


def _topic_for(query: str) -> list[str]:
    q = query.lower()
    topics = []
    for key, topic in (("setback", "setbacks"), ("far", "far"), ("coverage", "ground_coverage"),
                       ("height", "height"), ("parking", "parking"), ("fire", "fire_access")):
        if key in q:
            topics.append(topic)
    return topics or ["other"]


def _tool_call(name: str, args: dict) -> dict:
    return {"id": "call_" + uuid.uuid4().hex[:12], "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)}}


def _researcher_agent(messages: list[dict]) -> dict:
    last_user = max(i for i, m in enumerate(messages) if m["role"] == "user")
    user_text = messages[last_user].get("content") or ""
    after = messages[last_user + 1:]
    turns = sum(1 for m in after if m["role"] == "assistant")
    listed = re.findall(r"^\s*-\s+(.+)$", user_text, flags=re.M)
    if "MODIFIER CHECK" in user_text or "COVERAGE CHECK" in user_text:
        queries = [(_topic_for(q)[0], q.strip()) for q in listed[:3]]
    else:
        queries = DEFAULT_QUERIES
    if turns == 0 and queries:
        return {"content": None, "tool_calls": [_tool_call("search_corpus", {"query": q, "k": 4}) for _, q in queries]}
    if turns == 1:
        calls = []
        for m in after:
            if m["role"] != "tool":
                continue
            try:
                passages = json.loads(m.get("content") or "{}").get("passages", [])
            except json.JSONDecodeError:
                passages = []
            if passages:
                q = queries[min(len(calls), len(queries) - 1)][1] if queries else ""
                for topic in _topic_for(q):
                    calls.append(_tool_call("record_provision", {
                        "chunk_id": passages[0]["chunk_id"], "topic": topic,
                        "why_binding": "Top-ranked passage for this topic (stub)."}))
        if calls:
            return {"content": None, "tool_calls": calls}
    return {"content": None, "tool_calls": [_tool_call("finish_research", {"summary": "Stub research complete."})]}


def _assessor_findings(messages: list[dict]) -> dict:
    last = messages[-1].get("content") or ""
    is_retry = "FAILED verification" in last
    if STATE["mode"] == "hallucinate" or (STATE["mode"] == "hallucinate_once" and not is_retry):
        # Demo of self-verification: an unsupported answer citing text that was never retrieved.
        return {"content": json.dumps({"findings": [{
            "provision_id": "ZR2015:T99", "topic": "height", "requirement": "Height up to 30 m permitted",
            "required_value": 30, "proposed_value": 12.5, "unit": "m", "comparison": "<=", "status": "satisfied",
            "quote": "buildings up to 30 m are permitted on any road", "derivation": None,
            "explanation": "Fabricated finding (stub hallucination mode)."}],
            "conflicts": [], "exemption_signals": [], "insufficient_evidence": False, "missing_topics": []})}
    payload = _payload(next((m.get("content") or "" for m in messages if m["role"] == "user"), ""))
    findings = []
    for prov in payload.get("binding_provisions", [])[:8]:
        text = prov.get("text", "")
        findings.append({
            "provision_id": prov.get("chunk_id"), "topic": prov.get("topic", "other"),
            "requirement": text[:120], "required_value": None, "proposed_value": None, "unit": None,
            "comparison": "n/a", "status": "not_determinable", "quote": text[:80],
            "explanation": "Stub model: provision retrieved, no determination made.", "derivation": None,
        })
    return {"content": json.dumps({"findings": findings, "conflicts": [], "exemption_signals": [],
                                   "insufficient_evidence": False, "missing_topics": []})}


def _respond(task: str, messages: list[dict]) -> dict:
    if task == "researcher.agent":
        return _researcher_agent(messages)
    if task == "researcher.classify":
        use = re.search(r'"building_use":\s*"(\w+)"', messages[-1].get("content") or "")
        u = use.group(1) if use else ""
        category = ("residential" if u.startswith("residential") else "commercial" if u.startswith(("commercial", "hotel"))
                    else "mixed-use" if u.startswith("mixed") else "institutional" if u.startswith("institutional")
                    else "other")
        return {"content": json.dumps({"category": category, "entities": {}, "exemption_signals": [],
                                       "out_of_scope_signals": [], "rationale": "stub"})}
    if task == "researcher.modifiers":
        return {"content": json.dumps({"dependencies": [], "modifier_queries": [
            "maximum height of building restricted by road width",
            "setbacks for buildings above 11.5 m height"], "rationale": "stub"})}
    if task.startswith("assessor.findings"):
        return _assessor_findings(messages)
    return {"content": json.dumps({"ok": True})}


class ChatCompletionIn(BaseModel):
    model: str
    messages: list[dict]
    tools: list[dict] | None = None
    temperature: float | None = None
    max_tokens: int | None = None

    model_config = {"extra": "allow"}


@app.post("/v1/chat/completions")
async def completions(body: ChatCompletionIn):
    if STATE["mode"] == "down":
        return JSONResponse(status_code=503, content={"error": {"message": "stub provider down"}})
    await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX) + (120 if STATE["mode"] == "slow" else 0))
    system = next((m.get("content") or "" for m in body.messages if m["role"] == "system"), "")
    m = re.search(r"\[\[task:([\w.]+)\]\]", system)
    out = _respond(m.group(1) if m else "", body.messages)
    prompt_chars = sum(len(json.dumps(x)) for x in body.messages) + len(json.dumps(body.tools or []))
    completion_chars = len(json.dumps(out))
    return {
        "id": "stub-" + uuid.uuid4().hex[:10], "object": "chat.completion", "created": int(time.time()),
        "model": body.model,
        "choices": [{"index": 0, "finish_reason": "tool_calls" if out.get("tool_calls") else "stop",
                     "message": {"role": "assistant", **out}}],
        "usage": {"prompt_tokens": prompt_chars // 4, "completion_tokens": completion_chars // 4,
                  "total_tokens": (prompt_chars + completion_chars) // 4},
    }


class ModeIn(BaseModel):
    mode: str


@app.post("/admin/mode")
async def set_mode(body: ModeIn):
    if body.mode not in ("ok", "down", "slow", "hallucinate", "hallucinate_once"):
        return JSONResponse(status_code=400, content={"error": "mode must be ok|down|slow|hallucinate|hallucinate_once"})
    STATE["mode"] = body.mode
    return STATE


@app.get("/health")
async def health():
    return {"status": "ok", **STATE}
