"""Research agent (LangGraph). Finds every provision that binds the proposal.

    classify -> agent <-> tools -> post_finish -> modifier_check -> agent ...
                                          \-> coverage_check -> agent ...
                                          \-> handoff
    (any LLMUnavailable) -> fallback (deterministic retrieval, degraded) -> handoff

Retrieval is a tool the model chooses to call. Two explicit control steps make
this an agent rather than a pipeline (design approach steps 2-3): after the
model first declares itself done, `modifier_check` asks which recorded
provisions depend on variables that another provision might cap, and feeds
queries derived from the text it read back into the loop; `coverage_check`
sends it back with a different strategy if a mandatory topic is still empty.
The loop is bounded by model steps, tool calls and wall-clock time.
"""
from __future__ import annotations

import json
import time
from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from ..common.config import get_settings
from ..common.contracts import MANDATORY_TOPICS, USE_TO_CATEGORY, BuildingUse
from ..common.guardrails import wrap_untrusted
from ..common.observability import tracer
from ..common.prompts import load_prompt
from .runtime import AGENT_STEP_SECONDS, LLMUnavailable, RunContext, ToolFailure, llm_chat, parse_json, retriever_call

settings = get_settings()
TOPICS = ["setbacks", "far", "ground_coverage", "height", "use", "parking", "fire_access", "high_rise", "other"]

TOOLS: list[dict] = [
    {"type": "function", "function": {
        "name": "search_corpus",
        "description": "Search the BBMP bye-laws (BBL2003) and RMP-2015 zoning regulations (ZR2015). "
                       "Returns passages with chunk_id, clause label, context and text.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "What to look for"},
            "doc_id": {"type": "string", "enum": ["ZR2015", "BBL2003"], "description": "Restrict to one document"},
            "k": {"type": "integer", "description": "Number of passages (1-8, default 5)"},
            "mode": {"type": "string", "enum": ["hybrid", "lexical", "dense"],
                     "description": "lexical for exact words/numbers, dense for paraphrase, hybrid default"}},
            "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "get_clause",
        "description": "Fetch one clause by chunk_id, with sibling clauses of the same table/section.",
        "parameters": {"type": "object", "properties": {"chunk_id": {"type": "string"}}, "required": ["chunk_id"]}}},
    {"type": "function", "function": {
        "name": "follow_reference",
        "description": "Resolve a cross-reference such as 'Table 9', 'Table.23' or 'bye-law 16.0' to its passages.",
        "parameters": {"type": "object", "properties": {
            "reference": {"type": "string"},
            "doc_id": {"type": "string", "enum": ["ZR2015", "BBL2003"]}}, "required": ["reference"]}}},
    {"type": "function", "function": {
        "name": "get_proposal_field",
        "description": "Read a field of the validated proposal, e.g. 'road.abutting_road_width_m' or 'plot'.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "record_provision",
        "description": "Record a retrieved passage that binds this proposal (only ids returned by tools).",
        "parameters": {"type": "object", "properties": {
            "chunk_id": {"type": "string"},
            "topic": {"type": "string", "enum": TOPICS},
            "why_binding": {"type": "string"}}, "required": ["chunk_id", "topic", "why_binding"]}}},
    {"type": "function", "function": {
        "name": "finish_research",
        "description": "Declare research complete.",
        "parameters": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}}},
]

EXEMPTION_KEYWORDS = {
    "tdr": "Transfer of Development Rights (TDR) mentioned",
    "transfer of development": "Transfer of Development Rights (TDR) mentioned",
    "heritage": "heritage building/precinct mentioned",
    "exemption": "applicant mentions an exemption",
    "relaxation": "applicant mentions a relaxation",
    "concession": "applicant mentions a concession",
    "premium far": "premium/additional FAR mentioned",
    "additional far": "premium/additional FAR mentioned",
    "amalgamat": "plot amalgamation mentioned (additional FAR regime)",
    "aerodrome": "aerodrome height zone mentioned",
    "airport": "airport vicinity mentioned (aerodrome height limits)",
    "government building": "government/special building mentioned",
    "defence": "defence land/zone mentioned",
    "lake": "lake/water body buffer mentioned",
    "railway": "railway buffer mentioned",
    "road widening": "road widening / building line mentioned",
}
OUT_OF_SCOPE_KEYWORDS = {
    "outside bbmp": "site stated to be outside BBMP limits",
    "gram panchayat": "site under a gram panchayat (not BBMP)",
    "panchayat": "site under a panchayat (not BBMP)",
    "bmrda": "site under BMRDA (not BBMP corpus)",
    "mysuru": "different jurisdiction", "mysore": "different jurisdiction", "chennai": "different jurisdiction",
    "mumbai": "different jurisdiction", "hyderabad": "different jurisdiction",
    "telecom tower": "telecom tower (not covered by the indexed provisions)",
    "mobile tower": "telecom tower (not covered by the indexed provisions)",
    "helipad": "helipad (not covered by the indexed provisions)",
    "hoarding": "advertisement hoarding (not covered by the indexed provisions)",
    "underground metro": "metro infrastructure (not covered by the indexed provisions)",
    "mining": "mining/quarrying (not covered)",
}


class RState(TypedDict, total=False):
    proposal: dict
    notes_withheld: bool
    classification: dict
    category: str
    exemption_signals: list[str]
    out_of_scope_signals: list[str]
    messages: list[dict]
    passages: dict[str, dict]
    recorded: dict[str, dict]
    queries: list[dict]
    finished: bool
    modifier_rounds: int
    coverage_rounds: int
    nudges: int
    tool_failures: int
    budget_exhausted: bool
    degraded: bool
    degraded_reason: str
    followup: list[str]
    summary: str


def _ctx(config: RunnableConfig) -> RunContext:
    return config["configurable"]["ctx"]


def _proposal_view(state: RState) -> dict:
    p = dict(state["proposal"])
    p.pop("options", None)
    p.pop("client_reference", None)  # irrelevant to the assessment; keeping it would defeat the LLM cache
    notes = p.pop("notes", "")
    view = {"proposal": p}
    view["notes"] = "[withheld: flagged by input guardrail]" if state.get("notes_withheld") else wrap_untrusted(notes)
    return view


def _covered(state: RState) -> set[str]:
    topics: set[str] = set()
    for rec in state.get("recorded", {}).values():
        topics.update(rec["topics"])
    return topics


# --------------------------------------------------------------------- nodes
async def classify(state: RState, config: RunnableConfig) -> dict:
    ctx = _ctx(config)
    p = state["proposal"]
    declared = USE_TO_CATEGORY[BuildingUse(p["building_use"])].value
    notes = "" if state.get("notes_withheld") else (p.get("notes") or "")
    exempt = sorted({msg for kw, msg in EXEMPTION_KEYWORDS.items() if kw in notes.lower()})
    oos = sorted({msg for kw, msg in OUT_OF_SCOPE_KEYWORDS.items() if kw in notes.lower()})
    if p["zone"] == "other" or p["building_use"] == "other":
        oos.append(f"zone/use '{p['zone']}/{p['building_use']}' has no regulations in the indexed corpus")
    update: dict[str, Any] = {"category": declared, "exemption_signals": exempt, "out_of_scope_signals": oos,
                              "classification": {"declared_category": declared}}
    if state.get("followup"):
        return update
    prompt = load_prompt("researcher.classify", "v1")
    payload = json.dumps(_proposal_view(state), ensure_ascii=False)
    system, user = prompt.render(payload=payload)
    try:
        msg = await llm_chat(ctx, "classify", prompt, [{"role": "system", "content": system},
                                                         {"role": "user", "content": user}], json_mode=True, max_tokens=500)
    except LLMUnavailable as exc:
        return update | {"degraded": True, "degraded_reason": str(exc)}
    data = parse_json(msg.get("content")) or {}
    llm_cat = data.get("category")
    update["classification"] = {"declared_category": declared, "model_category": llm_cat,
                                "entities": data.get("entities", {}), "rationale": data.get("rationale")}
    if llm_cat and llm_cat != declared and llm_cat != "other":
        update["exemption_signals"] = exempt + [f"declared use '{p['building_use']}' but notes suggest '{llm_cat}'"]
    update["exemption_signals"] = sorted(set(update["exemption_signals"]) | {str(s) for s in data.get("exemption_signals", []) if s})
    update["out_of_scope_signals"] = sorted(set(oos) | {str(s) for s in data.get("out_of_scope_signals", []) if s})
    return update


async def start_agent(state: RState, config: RunnableConfig) -> dict:
    prompt = load_prompt("researcher.agent", "v1")
    view = _proposal_view(state)
    view["classification"] = state.get("classification", {})
    view["mandatory_topics"] = list(MANDATORY_TOPICS)
    view["also_consider"] = ["use", "parking", "high_rise", "fire_access"]
    system, user = prompt.render(payload=json.dumps(view, ensure_ascii=False))
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    if state.get("followup"):
        prior = [f"{cid} ({', '.join(r['topics'])})" for cid, r in state.get("recorded", {}).items()]
        messages.append({"role": "user", "content": "COVERAGE CHECK (requested by the assessment agent): the "
                         "provisions recorded so far were insufficient. Already recorded: " + "; ".join(prior) +
                         "\nRun these searches (try lexical mode and follow_reference), record what binds, then "
                         "call finish_research:\n" + "\n".join(f"- {q}" for q in state["followup"])})
    return {"messages": messages, "passages": state.get("passages", {}), "recorded": state.get("recorded", {}),
            "queries": state.get("queries", []), "finished": False, "modifier_rounds": 1 if state.get("followup") else 0,
            "coverage_rounds": 1 if state.get("followup") else 0, "nudges": 0, "tool_failures": 0}


async def agent(state: RState, config: RunnableConfig) -> dict:
    ctx = _ctx(config)
    if (ctx.steps >= settings.researcher_max_steps or ctx.tool_calls >= settings.researcher_max_tool_calls
            or ctx.remaining() < 8):
        await ctx.event("agent", "budget", name="loop_bound", status="exhausted",
                        payload={"steps": ctx.steps, "tool_calls": ctx.tool_calls, "remaining_s": ctx.remaining()})
        return {"budget_exhausted": True, "finished": True}
    prompt = load_prompt("researcher.agent", "v1")
    try:
        msg = await llm_chat(ctx, "agent", prompt, compact_history(state["messages"]), tools=TOOLS, max_tokens=900)
    except LLMUnavailable as exc:
        return {"degraded": True, "degraded_reason": str(exc)}
    ctx.steps += 1
    assistant = {"role": "assistant", "content": msg.get("content")}
    if msg.get("tool_calls"):
        assistant["tool_calls"] = msg["tool_calls"]
        return {"messages": state["messages"] + [assistant]}
    # The model answered in prose instead of calling tools.
    if state.get("nudges", 0) < 1:
        nudge = {"role": "user", "content": "Use the tools: record_provision for binding passages, then call "
                 "finish_research. Do not answer in prose."}
        return {"messages": state["messages"] + [assistant, nudge], "nudges": state.get("nudges", 0) + 1}
    return {"messages": state["messages"] + [assistant], "finished": True}


def compact_history(messages: list[dict]) -> list[dict]:
    """Context compaction (cost, L5): tool results older than the latest tool round are
    reduced to ids + labels. The model already acted on them; it can re-read any clause
    with get_clause. Without this the prompt grows with every turn and the research
    loop dominates the cost of a run."""
    if not settings.context_compaction_enabled:
        return messages
    last_assistant = max((i for i, m in enumerate(messages) if m["role"] == "assistant"), default=-1)
    out = []
    for i, m in enumerate(messages):
        if m["role"] == "tool" and i < last_assistant:
            try:
                data = json.loads(m.get("content") or "{}")
            except json.JSONDecodeError:
                data = {}
            if "passages" in data:
                brief = {"passages": [{"chunk_id": p["chunk_id"], "clause_label": p.get("clause_label")}
                                      for p in data["passages"]],
                         "note": "text elided from history; call get_clause to re-read a passage"}
                m = {**m, "content": json.dumps(brief, ensure_ascii=False)}
        out.append(m)
    return out


def _compact(p: dict) -> dict:
    return {"chunk_id": p["chunk_id"], "clause_label": p["clause_label"], "context": p.get("header"),
            "text": p["text"][:700], "refs": p.get("refs", [])}


def _get_path(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return {"error": f"no field '{path}'"}
    return cur


async def _run_tool(state: RState, ctx: RunContext, name: str, args: dict, passages: dict, recorded: dict,
                    queries: list) -> tuple[dict, bool]:
    finished = False
    if name == "search_corpus":
        q = str(args.get("query", ""))[:400]
        body = {"query": q, "k": max(1, min(int(args.get("k") or 5), 8)), "mode": args.get("mode") or "hybrid"}
        if args.get("doc_id") in ("ZR2015", "BBL2003"):
            body["doc_id"] = args["doc_id"]
        res = await retriever_call(ctx, "POST", "/v1/search", body)
        found = res.get("passages", [])
        queries.append({"query": q, "mode": body["mode"], "doc_id": body.get("doc_id"),
                        "results": [(p["chunk_id"], p.get("score")) for p in found]})
        for p in found:
            passages[p["chunk_id"]] = p
        return {"passages": [_compact(p) for p in found], "cached": res.get("cached")}, finished
    if name == "get_clause":
        res = await retriever_call(ctx, "GET", f"/v1/clause/{args.get('chunk_id', '')}")
        if "error" in res:
            return res, finished
        passages[res["chunk_id"]] = res
        return {"passages": [_compact(res)], "siblings": [
            {"chunk_id": n["chunk_id"], "clause_label": n["clause_label"], "text": n["text"][:300]}
            for n in res.get("neighbor_passages", [])]}, finished
    if name == "follow_reference":
        body = {"reference": str(args.get("reference", ""))[:100]}
        if args.get("doc_id") in ("ZR2015", "BBL2003"):
            body["doc_id"] = args["doc_id"]
        res = await retriever_call(ctx, "POST", "/v1/references", body)
        found = res.get("passages", [])
        for p in found:
            passages[p["chunk_id"]] = p
        queries.append({"reference": body["reference"], "results": [(p["chunk_id"], None) for p in found]})
        return {"passages": [_compact(p) for p in found]}, finished
    if name == "get_proposal_field":
        view = _proposal_view(state)
        path = str(args.get("path", ""))
        if path.startswith("notes"):
            return {"notes": view["notes"]}, finished
        return {"path": path, "value": _get_path(view["proposal"], path)}, finished
    if name == "record_provision":
        cid = str(args.get("chunk_id", ""))
        topic = args.get("topic") if args.get("topic") in TOPICS else "other"
        if cid not in passages:
            return {"error": f"unknown chunk_id '{cid}': only ids returned by search_corpus, get_clause or "
                             "follow_reference can be recorded"}, finished
        rec = recorded.setdefault(cid, {"topics": [], "why": []})
        if topic not in rec["topics"]:
            rec["topics"].append(topic)
        rec["why"].append(str(args.get("why_binding", ""))[:300])
        return {"recorded": cid, "topic": topic, "total_recorded": len(recorded)}, finished
    if name == "finish_research":
        return {"ok": True}, True
    return {"error": f"unknown tool '{name}'"}, finished


async def tools(state: RState, config: RunnableConfig) -> dict:
    ctx = _ctx(config)
    last = state["messages"][-1]
    passages = dict(state.get("passages", {}))
    recorded = {k: {"topics": list(v["topics"]), "why": list(v["why"])} for k, v in state.get("recorded", {}).items()}
    queries = list(state.get("queries", []))
    new_messages: list[dict] = []
    finished = False
    failures = state.get("tool_failures", 0)
    for call in last.get("tool_calls", []):
        fn = call.get("function", {})
        name = fn.get("name", "")
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {}
        if ctx.tool_calls >= settings.researcher_max_tool_calls:
            result, done = {"error": "tool-call budget exhausted; call finish_research"}, False
        else:
            ctx.tool_calls += 1
            start = time.perf_counter()
            with tracer().start_as_current_span(f"researcher.tool.{name}") as span:
                span.set_attribute("tool.args", json.dumps(args)[:500])
                try:
                    result, done = await _run_tool(state, ctx, name, args, passages, recorded, queries)
                    status = "error" if "error" in result else "ok"
                    failures = 0 if status == "ok" else failures
                except ToolFailure as exc:
                    result, done, status = {"error": str(exc)}, False, "error"
                    failures += 1
            elapsed = (time.perf_counter() - start) * 1000
            AGENT_STEP_SECONDS.labels("researcher", f"tool.{name}").observe(elapsed / 1000)
            ids = [p["chunk_id"] for p in result.get("passages", [])] if isinstance(result, dict) else []
            await ctx.event("tools", "tool_call", name=name, status=status, latency_ms=elapsed,
                            payload={"args": args, "result_chunk_ids": ids,
                                     "result": {k: v for k, v in result.items() if k != "passages"},
                                     "passage_scores": [(p["chunk_id"], p.get("score"), p.get("dense_score"))
                                                        for p in passages.values() if p["chunk_id"] in ids]})
        finished = finished or done
        new_messages.append({"role": "tool", "tool_call_id": call.get("id", ""),
                             "content": json.dumps(result, ensure_ascii=False)})
    update: dict[str, Any] = {"messages": state["messages"] + new_messages, "passages": passages,
                              "recorded": recorded, "queries": queries, "finished": finished,
                              "tool_failures": failures}
    if failures >= 3:
        update.update(finished=True, budget_exhausted=True)
        await ctx.event("tools", "budget", name="retriever_failures", status="exhausted",
                        payload={"consecutive_failures": failures})
    return update


def _variable_queries(state: RState) -> list[str]:
    """Variable-interaction expansion: for each recorded topic, ask whether a
    controlling variable of the proposal caps it elsewhere."""
    covered = _covered(state)
    variables = ["road width", "building height", "plot size"]
    out = []
    for topic in ("height", "far", "setbacks"):
        if topic in covered or topic == "height":
            for var in variables:
                if (topic, var) in {("height", "building height"), ("setbacks", "plot size")}:
                    continue
                label = {"far": "FAR", "height": "maximum height of building", "setbacks": "setbacks"}[topic]
                out.append(f"{label} restricted by {var}")
    return out[:4]


async def modifier_check(state: RState, config: RunnableConfig) -> dict:
    ctx = _ctx(config)
    recorded = state.get("recorded", {})
    passages = state.get("passages", {})
    refs = sorted({r for cid in recorded for r in passages.get(cid, {}).get("refs", [])
                   if r.split(":")[1] not in {cid.split(":")[1] for cid in recorded}})
    prompt = load_prompt("researcher.modifiers", "v1")
    payload = {"proposal": _proposal_view(state)["proposal"],
               "recorded": [{"chunk_id": cid, "topics": r["topics"], "clause_label": passages[cid]["clause_label"],
                             "text": passages[cid]["text"][:600]} for cid, r in recorded.items() if cid in passages]}
    system, user = prompt.render(payload=json.dumps(payload, ensure_ascii=False))
    try:
        msg = await llm_chat(ctx, "modifier_check", prompt, [{"role": "system", "content": system},
                                                                {"role": "user", "content": user}],
                             json_mode=True, max_tokens=600)
    except LLMUnavailable as exc:
        return {"degraded": True, "degraded_reason": str(exc)}
    data = parse_json(msg.get("content")) or {}
    queries = [str(q)[:200] for q in data.get("modifier_queries", [])][:5]
    queries += [q for q in _variable_queries(state) if q not in queries]
    follow = sorted(set(refs) | {str(r) for r in data.get("references_to_follow", [])})[:6]
    await ctx.event("modifier_check", "control", name="modifier_check",
                    payload={"llm_queries": data.get("modifier_queries", []), "variable_queries": _variable_queries(state),
                             "references": follow, "dependencies": data.get("dependencies", [])})
    text = ("MODIFIER CHECK: before finishing, look for provisions stated elsewhere that modify or cap the ones "
            "you recorded (notes under other tables, limits by road width, height thresholds that switch tables, "
            "zone-specific notes). Run these searches, follow these references, record anything that binds this "
            "proposal, then call finish_research again.\n"
            + "\n".join(f"- {q}" for q in queries)
            + ("\nReferences to follow: " + ", ".join(follow) if follow else ""))
    return {"messages": state["messages"] + [{"role": "user", "content": text}], "finished": False,
            "modifier_rounds": state.get("modifier_rounds", 0) + 1}


async def coverage_check(state: RState, config: RunnableConfig) -> dict:
    ctx = _ctx(config)
    missing = [t for t in MANDATORY_TOPICS if t not in _covered(state)]
    p = state["proposal"]
    hints = {
        "setbacks": f"setbacks width of site depth of site building height {p['building']['proposed_height_m']} m",
        "far": f"FAR road width {p['road']['abutting_road_width_m']} m plot size {p['plot']['area_sqm']} sq.m",
        "ground_coverage": f"ground coverage plot size {p['plot']['area_sqm']} sq.m {p['zone'].replace('_', ' ')}",
        "height": f"maximum height road width {p['road']['abutting_road_width_m']} m",
    }
    await ctx.event("coverage_check", "control", name="coverage_check", payload={"missing": missing})
    text = ("COVERAGE CHECK: no provision has been recorded yet for: " + ", ".join(missing) +
            ". Try a different strategy: lexical mode with the exact words a regulation would use, restrict to "
            "one document, or follow_reference to the zone's tables. Suggested queries:\n"
            + "\n".join(f"- {hints[t]}" for t in missing))
    return {"messages": state["messages"] + [{"role": "user", "content": text}], "finished": False,
            "coverage_rounds": state.get("coverage_rounds", 0) + 1}


async def fallback(state: RState, config: RunnableConfig) -> dict:
    """Degradation path: no model available. Deterministic, templated retrieval so the
    caller still gets the candidate provisions (never a determination)."""
    ctx = _ctx(config)
    p = state["proposal"]
    zone = p["zone"].replace("_", " ")
    plan = [
        ("setbacks", f"setbacks width of site depth of site height {p['building']['proposed_height_m']} m"),
        ("far", f"FAR ground coverage {zone} plot size {p['plot']['area_sqm']} road width {p['road']['abutting_road_width_m']}"),
        ("height", f"maximum height of building road width {p['road']['abutting_road_width_m']} m"),
        ("parking", f"parking requirements {p['building_use'].replace('_', ' ')}"),
    ]
    passages = dict(state.get("passages", {}))
    recorded = {k: {"topics": list(v["topics"]), "why": list(v["why"])} for k, v in state.get("recorded", {}).items()}
    queries = list(state.get("queries", []))
    for topic, q in plan:
        if ctx.remaining() < 3:
            break
        try:
            res = await retriever_call(ctx, "POST", "/v1/search", {"query": q, "k": 3, "mode": "hybrid"})
        except ToolFailure as exc:
            await ctx.event("fallback", "tool_call", name="search_corpus", status="error", payload={"error": str(exc)})
            continue
        ctx.tool_calls += 1
        found = res.get("passages", [])
        queries.append({"query": q, "mode": "hybrid", "results": [(x["chunk_id"], x.get("score")) for x in found],
                        "fallback": True})
        await ctx.event("fallback", "tool_call", name="search_corpus", payload={"args": {"query": q},
                        "result_chunk_ids": [x["chunk_id"] for x in found]})
        for x in found[:2]:
            passages[x["chunk_id"]] = x
            rec = recorded.setdefault(x["chunk_id"], {"topics": [], "why": []})
            if topic not in rec["topics"]:
                rec["topics"].append(topic)
            rec["why"].append("candidate (degraded mode, not model-selected)")
    return {"passages": passages, "recorded": recorded, "queries": queries, "degraded": True, "finished": True}


async def handoff(state: RState, config: RunnableConfig) -> dict:
    return {"summary": f"{len(state.get('recorded', {}))} provisions recorded"}


# -------------------------------------------------------------------- wiring
def _after_classify(state: RState) -> str:
    return "fallback" if state.get("degraded") else "start_agent"


def _after_agent(state: RState) -> str:
    if state.get("degraded"):
        return "fallback"
    if state.get("finished"):
        return "post_finish"
    last = state["messages"][-1]
    return "tools" if last.get("tool_calls") else "agent"


def _after_tools(state: RState) -> str:
    return "post_finish" if state.get("finished") else "agent"


def _post_finish(state: RState) -> str:
    if state.get("degraded"):
        return "fallback"
    if state.get("budget_exhausted"):
        return "handoff"
    if settings.modifier_search_enabled and state.get("modifier_rounds", 0) == 0 and state.get("recorded"):
        return "modifier_check"
    missing = [t for t in MANDATORY_TOPICS if t not in _covered(state)]
    if missing and state.get("coverage_rounds", 0) == 0:
        return "coverage_check"
    return "handoff"


async def post_finish(state: RState, config: RunnableConfig) -> dict:
    return {}


def _after_control(state: RState) -> str:
    return "fallback" if state.get("degraded") else "agent"


def build_graph():
    g = StateGraph(RState)
    for name, fn in (("classify", classify), ("start_agent", start_agent), ("agent", agent), ("tools", tools),
                     ("post_finish", post_finish), ("modifier_check", modifier_check),
                     ("coverage_check", coverage_check), ("fallback", fallback), ("handoff", handoff)):
        g.add_node(name, fn)
    g.add_edge(START, "classify")
    g.add_conditional_edges("classify", _after_classify, ["fallback", "start_agent"])
    g.add_edge("start_agent", "agent")
    g.add_conditional_edges("agent", _after_agent, ["fallback", "post_finish", "tools", "agent"])
    g.add_conditional_edges("tools", _after_tools, ["post_finish", "agent"])
    g.add_conditional_edges("post_finish", _post_finish, ["fallback", "handoff", "modifier_check", "coverage_check"])
    g.add_conditional_edges("modifier_check", _after_control, ["fallback", "agent"])
    g.add_conditional_edges("coverage_check", _after_control, ["fallback", "agent"])
    g.add_edge("fallback", "handoff")
    g.add_edge("handoff", END)
    return g.compile()


GRAPH = build_graph()


def build_dossier(state: RState, ctx: RunContext) -> dict:
    passages = state.get("passages", {})
    recorded = state.get("recorded", {})
    binding = []
    for cid, rec in recorded.items():
        p = passages.get(cid)
        if p:
            binding.append({"chunk_id": cid, "doc_id": p["doc_id"], "clause_label": p["clause_label"],
                            "page": p.get("page"), "header": p.get("header"), "text": p["text"],
                            "topics": rec["topics"], "why": rec["why"][:3]})
    others = sorted((p for cid, p in passages.items() if cid not in recorded),
                    key=lambda p: p.get("score") or 0, reverse=True)[:10]
    return {
        "binding": binding,
        "other_retrieved": [{"chunk_id": p["chunk_id"], "doc_id": p["doc_id"], "clause_label": p["clause_label"],
                             "page": p.get("page"), "header": p.get("header"), "text": p["text"]} for p in others],
        "all_retrieved_ids": sorted(passages),
        "queries": state.get("queries", []),
        "category": state.get("category"),
        "classification": state.get("classification", {}),
        "exemption_signals": state.get("exemption_signals", []),
        "out_of_scope_signals": state.get("out_of_scope_signals", []),
        "covered_topics": sorted(_covered(state)),
        "missing_topics": [t for t in MANDATORY_TOPICS if t not in _covered(state)],
        "degraded": bool(state.get("degraded")),
        "degraded_reason": state.get("degraded_reason"),
        "budget_exhausted": bool(state.get("budget_exhausted")),
        "steps": ctx.steps, "tool_calls": ctx.tool_calls, "llm_calls": ctx.llm_calls,
        "modifier_rounds": state.get("modifier_rounds", 0), "coverage_rounds": state.get("coverage_rounds", 0),
        "prompt_versions": ctx.prompt_versions,
    }

