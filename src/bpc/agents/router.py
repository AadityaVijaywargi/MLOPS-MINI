"""Deterministic routing (F6/F7). The model never chooses the route: it only
produces findings; this function maps verified findings + flags to one of the
three routes and states why. Escalation conditions are checked before any
determination, so a proposal that touches an exemption, a conflict or
something outside the corpus is never answered."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..common.contracts import MANDATORY_TOPICS, Route

# Declared precedence (corpus/manifest.yaml): ZR2015 governs these topics.
ZR_GOVERNS = {"setbacks", "far", "ground_coverage", "height", "use"}


@dataclass
class RouteDecision:
    route: Route
    reason: str
    escalation_reasons: list[str] = field(default_factory=list)
    superseded: list[int] = field(default_factory=list)
    resolved_conflicts: list[str] = field(default_factory=list)


def apply_precedence(findings: list[dict]) -> list[int]:
    """BBL2003 findings on a topic ZR2015 governs are superseded when ZR2015 also
    has a finding on that topic. Returns indices of superseded findings."""
    zr_topics = {f["topic"] for f in findings if f["provision_id"].startswith("ZR2015:")
                 and f["status"] in ("satisfied", "violated")}
    return [i for i, f in enumerate(findings) if f["provision_id"].startswith("BBL2003:")
            and f["topic"] in ZR_GOVERNS and f["topic"] in zr_topics]


def resolve_conflicts(conflicts: list[dict]) -> tuple[list[str], list[str]]:
    unresolved, resolved = [], []
    for c in conflicts:
        ids = c.get("provision_ids") or []
        docs = {i.split(":")[0] for i in ids}
        desc = c.get("description") or "conflicting provisions"
        if docs == {"ZR2015", "BBL2003"} and c.get("topic") in ZR_GOVERNS:
            resolved.append(f"{desc} -> RMP-2015 ZR applies (declared precedence for {c.get('topic')})")
        else:
            unresolved.append(f"{desc} ({', '.join(ids)})")
    return unresolved, resolved


def decide(
    findings: list[dict],
    *,
    flags: list[str],
    conflicts: list[dict],
    exemption_signals: list[str],
    out_of_scope_signals: list[str],
    missing_topics: list[str],
    verification_failed: bool,
    withheld: int,
    degraded: bool,
    budget_exhausted: bool,
) -> RouteDecision:
    superseded = apply_precedence(findings)
    active = [f for i, f in enumerate(findings) if i not in superseded]
    unresolved, resolved = resolve_conflicts(conflicts)

    def esc(reason: str, reasons: list[str]) -> RouteDecision:
        return RouteDecision(Route.specialist, reason, reasons, superseded, resolved)

    if degraded:
        return esc("Model provider unavailable (circuit open / outage): candidate provisions were retrieved but "
                   "no finding was made. Degraded mode - a person must assess.", ["llm_unavailable"])
    guard = [f for f in flags if f in ("prompt_injection_suspected", "toxic_content")]
    if guard:
        return esc("Input guardrail flagged the free-text notes (" + ", ".join(guard) + "); notes were withheld "
                   "from the agents and the proposal needs human review.", guard)
    if out_of_scope_signals:
        return esc("Proposal falls outside the indexed corpus: " + "; ".join(out_of_scope_signals), out_of_scope_signals)
    if unresolved:
        return esc("Provisions conflict and no declared precedence resolves it: " + "; ".join(unresolved), unresolved)
    if exemption_signals:
        return esc("An exemption or special regime may apply: " + "; ".join(exemption_signals), exemption_signals)
    violated = [f for f in active if f["status"] == "violated"]
    if violated:
        labels = sorted({f["clause_label"] for f in violated})
        return RouteDecision(Route.revise, "Violates " + ", ".join(labels) + ". Revise the proposal and re-check.",
                             [], superseded, resolved)
    gaps = list(missing_topics)
    undetermined = sorted({f["topic"] for f in active if f["status"] == "not_determinable"
                           and f["topic"] in MANDATORY_TOPICS})
    if verification_failed or withheld or gaps or undetermined or budget_exhausted:
        reasons = []
        if withheld:
            reasons.append(f"{withheld} finding(s) failed self-verification and were withheld")
        if gaps:
            reasons.append("no verified finding for: " + ", ".join(gaps))
        if undetermined:
            reasons.append("could not determine: " + ", ".join(undetermined))
        if budget_exhausted:
            reasons.append("research budget exhausted before completion")
        return esc("Insufficient verified evidence to route automatically: " + "; ".join(reasons), reasons)
    return RouteDecision(Route.clear, "Every mandatory topic has a verified finding and no provision is violated. "
                         "Clear for submission, subject to professional review.", [], superseded, resolved)
