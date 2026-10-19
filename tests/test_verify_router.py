from bpc.agents.router import decide
from bpc.agents.verify import safe_eval, verify_findings
from bpc.common.contracts import MANDATORY_TOPICS, Route

PASSAGES = {
    "ZR2015:T10:ii.b": {"chunk_id": "ZR2015:T10:ii.b", "doc_id": "ZR2015", "clause_label": "x",
                        "text": "b) If the road width is less than 9.0 m, then the maximum height is restricted to "
                                "11.5 meters\nor Stilt +GF+2 floors"},
    "ZR2015:T8": {"chunk_id": "ZR2015:T8", "doc_id": "ZR2015", "clause_label": "y",
                  "text": "Table 8: Setbacks\nAbove 9.0 m 8 % 8% 12% 8 %"},
}
PROPOSAL = {"plot": {"width_m": 9, "depth_m": 12, "area_sqm": 108}, "building": {"proposed_height_m": 12.5},
            "setbacks": {"front_m": 1.5}}


def f(**kw):
    base = {"provision_id": "ZR2015:T10:ii.b", "topic": "height", "status": "violated", "comparison": "<=",
            "required_value": 11.5, "proposed_value": 12.5, "quote": "the maximum height is restricted to 11.5 meters",
            "clause_label": "ZR T10 (ii)(b)"}
    base.update(kw)
    return base


def test_verbatim_quote_with_pdf_spacing_passes():
    rep = verify_findings([f(quote="maximum height is restricted  to 11.5 meters or Stilt +GF+2")],
                          PASSAGES, PROPOSAL, ("height",))
    assert rep.passed, rep.errors()


def test_unresolved_citation_and_fabricated_quote_fail():
    rep = verify_findings([f(provision_id="ZR2015:T99"), f(quote="up to 30 m allowed")], PASSAGES, PROPOSAL, ("height",))
    errs = " ".join(rep.errors())
    assert "citation_unresolved" in errs and "quote_not_in_passage" in errs
    assert rep.hallucination_rate == 1.0


def test_untraceable_number_and_inconsistent_status():
    rep = verify_findings([f(required_value=15.0), f(status="satisfied")], PASSAGES, PROPOSAL, ("height",))
    errs = " ".join(rep.errors())
    assert "number_untraceable" in errs and "status_inconsistent" in errs


def test_derivation_from_percentage():
    finding = f(provision_id="ZR2015:T8", topic="setbacks", quote="Above 9.0 m 8 % 8% 12% 8 %", required_value=1.44,
                proposed_value=1.5, comparison=">=", status="satisfied", derivation="12% * 12")
    rep = verify_findings([finding], PASSAGES, PROPOSAL, ("setbacks",))
    assert rep.passed, rep.errors()
    assert abs(safe_eval("0.12 x 12") - 1.44) < 1e-9
    assert safe_eval("max(1.0, 0.08 * 9)") == 1.0


def _decide(findings, **kw):
    args = dict(flags=[], conflicts=[], exemption_signals=[], out_of_scope_signals=[], missing_topics=[],
                verification_failed=False, withheld=0, degraded=False, budget_exhausted=False)
    args.update(kw)
    return decide(findings, **args)


def _ok(topic, status="satisfied", pid="ZR2015:T10"):
    return {"provision_id": pid, "topic": topic, "status": status, "clause_label": pid}


def test_route_clear_revise_specialist():
    clear = [_ok(t) for t in MANDATORY_TOPICS]
    assert _decide(clear).route == Route.clear
    assert _decide(clear + [_ok("height", "violated", "ZR2015:T10:ii.b")]).route == Route.revise
    assert _decide(clear, exemption_signals=["TDR"]).route == Route.specialist
    assert _decide(clear, flags=["prompt_injection_suspected"]).route == Route.specialist
    assert _decide(clear, degraded=True).route == Route.specialist
    assert _decide(clear[:2], missing_topics=["ground_coverage", "height"]).route == Route.specialist


def test_precedence_supersedes_byelaw_on_governed_topic():
    findings = [_ok(t) for t in MANDATORY_TOPICS] + [_ok("setbacks", "violated", "BBL2003:T5")]
    d = _decide(findings)
    assert d.route == Route.clear and d.superseded == [4]


def test_unresolved_conflict_escalates():
    conflicts = [{"provision_ids": ["BBL2003:s16.0", "BBL2003:T13"], "topic": "parking", "description": "differ"}]
    assert _decide([_ok(t) for t in MANDATORY_TOPICS], conflicts=conflicts).route == Route.specialist
