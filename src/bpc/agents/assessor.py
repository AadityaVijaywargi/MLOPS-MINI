"""Assessment agent (LangGraph). Turns the research dossier into per-provision
findings, verifies them against the retrieved text, and routes.

    assess -> verify -> route                       (verified)
                     -> assess   (retry, strict re-quote strategy, bounded)
                     -> handback (ask the research agent for more, bounded)
                     -> route    (still failing -> withheld + escalation)
    degraded dossier -> route (no model call, specialist review)
"""
from __future__ import annotations

import json
from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from ..common.config import get_settings
from ..common.contracts import MANDATORY_TOPICS, Citation, Escalation, Finding, Route, RunResult
from ..common.guardrails import filter_output_text, wrap_untrusted
from ..common.prompts import assessor_variant, load_prompt
from .router import decide
from .runtime import LLMUnavailable, RunContext, llm_chat, parse_json
from .verify import verify_findings

settings = get_settings()


class AState(TypedDict, total=False):
    run_id: str
    proposal: dict
    dossier: dict
    variant: str
    flags: list[str]
    handbacks: int
    raw: dict | None
    raw_text: str | None
    findings: list[dict]
    conflicts: list[dict]
    exemption_signals: list[str]
    missing_topics: list[str]
    insufficient: bool
    attempts: int
    feedback: str | None
    report: dict
    ok_idx: list[int]
    handback: bool
    handback_queries: list[str]
    degraded: bool
    degraded_reason: str
    result: dict


def _ctx(config: RunnableConfig) -> RunContext:
    return config["configurable"]["ctx"]


def _passages(dossier: dict) -> dict[str, dict]:
    out = {p["chunk_id"]: p for p in dossier.get("other_retrieved", [])}
    out.update({p["chunk_id"]: p for p in dossier.get("binding", [])})
    return out


def _proposal_view(state: AState) -> dict:
    p = dict(state["proposal"])
    p.pop("options", None)
    p.pop("client_reference", None)  # irrelevant to the assessment; keeping it would defeat the LLM cache
    notes = p.pop("notes", "")
    withheld = any(f in state.get("flags", []) for f in ("prompt_injection_suspected", "toxic_content"))
    return {"proposal": p, "notes": "[withheld: flagged by input guardrail]" if withheld else wrap_untrusted(notes)}


async def assess(state: AState, config: RunnableConfig) -> dict:
    ctx = _ctx(config)
    dossier = state["dossier"]
    if dossier.get("degraded"):
        return {"degraded": True, "degraded_reason": dossier.get("degraded_reason") or "research ran degraded"}
    prompt = load_prompt("assessor.findings", state["variant"])
    payload = _proposal_view(state) | {
        "category": dossier.get("category"),
        "binding_provisions": [{"chunk_id": b["chunk_id"], "clause_label": b["clause_label"],
                                "topic": b["topics"][0] if b["topics"] else "other", "topics": b["topics"],
                                "context": b.get("header"), "why_binding": b.get("why", [])[:2], "text": b["text"]}
                               for b in dossier.get("binding", [])],
        "other_retrieved": [{"chunk_id": o["chunk_id"], "clause_label": o["clause_label"],
                             "context": o.get("header"), "text": o["text"][:600]}
                            for o in dossier.get("other_retrieved", [])[:6]],
        "precedence": "Where RMP-2015 ZR (ZR2015) and the 2003 bye-laws (BBL2003) both regulate setbacks, FAR, "
                      "ground coverage, height or use, ZR2015 governs (declared). Report any other conflict.",
        "mandatory_topics": list(MANDATORY_TOPICS),
    }
    system, user = prompt.render(payload=json.dumps(payload, ensure_ascii=False))
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    if state.get("feedback"):
        messages += [{"role": "assistant", "content": state.get("raw_text") or ""},
                     {"role": "user", "content": state["feedback"]}]
    attempts = state.get("attempts", 0) + 1
    try:
        msg = await llm_chat(ctx, "assess" if attempts == 1 else f"assess_retry{attempts - 1}", prompt, messages,
                             json_mode=True, max_tokens=3000)
    except LLMUnavailable as exc:
        return {"degraded": True, "degraded_reason": str(exc), "attempts": attempts}
    ctx.steps += 1
    raw = parse_json(msg.get("content"))
    topics = {b["chunk_id"]: (b["topics"][0] if b["topics"] else "other") for b in dossier.get("binding", [])}
    findings = []
    for f in (raw or {}).get("findings", []) or []:
        if not isinstance(f, dict):
            continue
        f.setdefault("topic", topics.get(f.get("provision_id"), "other"))
        f.setdefault("explanation", "")
        f.setdefault("requirement", "")
        findings.append(f)
    return {"raw": raw, "raw_text": msg.get("content"), "findings": findings, "attempts": attempts,
            "conflicts": (raw or {}).get("conflicts", []) or [],
            "exemption_signals": [str(s) for s in (raw or {}).get("exemption_signals", []) or [] if s],
            "missing_topics": [str(s) for s in (raw or {}).get("missing_topics", []) or [] if s],
            "insufficient": bool((raw or {}).get("insufficient_evidence")), "feedback": None}


async def verify(state: AState, config: RunnableConfig) -> dict:
    ctx = _ctx(config)
    if state.get("degraded"):
        return {}
    passages = _passages(state["dossier"])
    report = verify_findings(state.get("findings", []), passages, state["proposal"], MANDATORY_TOPICS)
    ok_idx = [c.index for c in report.checks if c.ok]
    rep = report.to_dict() | {"attempt": state.get("attempts", 1), "parse_ok": state.get("raw") is not None,
                              "verified_findings": len(ok_idx)}
    await ctx.event("verify", "verification", name="self_verification",
                    status="passed" if report.passed else "failed", payload=rep)
    update: dict[str, Any] = {"report": rep, "ok_idx": ok_idx}
    finding_errors = [e for e in report.errors() if e.startswith("finding[")]
    if (state.get("raw") is None or finding_errors) and state.get("attempts", 1) <= settings.assessor_max_verification_retries:
        update["feedback"] = (
            "Your previous answer FAILED verification against the retrieved passages:\n- "
            + "\n- ".join((finding_errors or ["output was not valid JSON"])[:12])
            + "\nStrategy change: for every finding copy the quote character-for-character from the provision text "
              "with that exact chunk_id, cite only chunk_ids present in the payload, use only numbers from the quote "
              "or the proposal (write the arithmetic in derivation), and make status agree with the comparison. "
              "Drop any finding you cannot support. Return the complete JSON again."
        )
    return update


def _after_verify(state: AState) -> str:
    if state.get("degraded"):
        return "route"
    if state.get("feedback"):
        return "assess"
    rep = state.get("report", {})
    missing = [e for e in rep.get("errors", []) if e.startswith("missing mandatory topic")]
    if (missing or state.get("insufficient")) and state.get("handbacks", 0) < settings.assessor_max_research_handbacks:
        return "handback"
    return "route"


async def handback(state: AState, config: RunnableConfig) -> dict:
    ctx = _ctx(config)
    rep = state.get("report", {})
    missing = [e.split(": ", 1)[1] for e in rep.get("errors", []) if e.startswith("missing mandatory topic")]
    missing += [t for t in state.get("missing_topics", []) if t not in missing]
    p = state["proposal"]
    hints = {
        "setbacks": f"setbacks for building height {p['building']['proposed_height_m']} m width and depth of site",
        "far": f"FAR {p['zone'].replace('_', ' ')} road width {p['road']['abutting_road_width_m']} m plot size",
        "ground_coverage": f"ground coverage {p['zone'].replace('_', ' ')} plot size {p['plot']['area_sqm']} sq.m",
        "height": f"height of building limited by road width {p['road']['abutting_road_width_m']} m",
    }
    queries = [hints.get(t, f"{t} requirements") for t in missing] or ["provisions binding this proposal"]
    await ctx.event("handback", "handoff", name="assessor->researcher", payload={"missing": missing, "queries": queries})
    return {"handback": True, "handback_queries": queries}


def _citation(p: dict, quote: str) -> Citation:
    return Citation(chunk_id=p["chunk_id"], doc_id=p["doc_id"], clause_label=p["clause_label"], page=p.get("page"),
                    quote=quote, passage_text=p["text"])


async def route(state: AState, config: RunnableConfig) -> dict:
    ctx = _ctx(config)
    dossier = state["dossier"]
    passages = _passages(dossier)
    findings_raw = state.get("findings", [])
    ok = set(state.get("ok_idx", []))
    verified = [findings_raw[i] for i in sorted(ok)]
    withheld = len(findings_raw) - len(verified)
    rep = state.get("report", {})
    missing = [e.split(": ", 1)[1] for e in rep.get("errors", []) if e.startswith("missing mandatory topic")]
    flags = list(state.get("flags", []))
    decision = decide(
        verified,
        flags=flags,
        conflicts=state.get("conflicts", []),
        exemption_signals=sorted(set(dossier.get("exemption_signals", [])) | set(state.get("exemption_signals", []))),
        out_of_scope_signals=dossier.get("out_of_scope_signals", []),
        missing_topics=missing,
        verification_failed=bool(rep) and not rep.get("passed", False),
        withheld=withheld,
        degraded=bool(state.get("degraded")),
        budget_exhausted=bool(dossier.get("budget_exhausted")),
    )
    out_findings: list[Finding] = []
    filtered: list[str] = []
    for i, f in enumerate(verified):
        p = passages[f["provision_id"]]
        expl, v1 = filter_output_text(str(f.get("explanation", "")))
        req, v2 = filter_output_text(str(f.get("requirement", "")))
        filtered += v1 + v2
        if i in decision.superseded:
            expl += " (Superseded: RMP-2015 ZR governs this topic per declared precedence.)"
        out_findings.append(Finding(
            provision_id=f["provision_id"], topic=str(f.get("topic", "other")), clause_label=p["clause_label"],
            requirement=req, required_value=f.get("required_value") if isinstance(f.get("required_value"), (int, float)) else None,
            proposed_value=f.get("proposed_value") if isinstance(f.get("proposed_value"), (int, float)) else None,
            unit=f.get("unit"), comparison=f.get("comparison"), status=f["status"], explanation=expl,
            derivation=f.get("derivation"), citations=[_citation(p, f.get("quote", ""))], verified=True,
        ))
    reason, v3 = filter_output_text(decision.reason)
    filtered += v3
    if filtered:
        flags.append("output_filtered")
        await ctx.event("route", "guardrail", name="output_filter", status="modified", payload={"violations": filtered})
    candidates = []
    if decision.route == Route.specialist:
        for b in dossier.get("binding", [])[:12]:
            candidates.append(_citation(b, b["text"][:200]))
    escalation = Escalation(required=decision.route == Route.specialist, reasons=decision.escalation_reasons)
    result = RunResult(
        run_id=state["run_id"], status="escalated" if decision.route == Route.specialist else "completed",
        route=decision.route, reason=reason, category=dossier.get("category"), findings=out_findings,
        candidate_provisions=candidates, withheld_findings=withheld, escalation=escalation,
        flags=sorted(set(flags)), degraded=bool(state.get("degraded")),
        prompt_versions={**dossier.get("prompt_versions", {}), **ctx.prompt_versions},
    )
    await ctx.event("route", "route", name=decision.route.value, payload={
        "reason": reason, "escalation_reasons": decision.escalation_reasons, "superseded": decision.superseded,
        "resolved_conflicts": decision.resolved_conflicts, "verified_findings": len(out_findings),
        "withheld_findings": withheld})
    return {"result": result.model_dump(mode="json")}


def build_graph():
    g = StateGraph(AState)
    g.add_node("assess", assess)
    g.add_node("verify", verify)
    g.add_node("handback", handback)
    g.add_node("route", route)
    g.add_edge(START, "assess")
    g.add_edge("assess", "verify")
    g.add_conditional_edges("verify", _after_verify, ["assess", "handback", "route"])
    g.add_edge("handback", END)
    g.add_edge("route", END)
    return g.compile()


GRAPH = build_graph()


def variant_for(proposal: dict) -> str:
    return assessor_variant((proposal.get("options") or {}).get("prompt_variant"))
