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
            "required_value": 11.5, "proposed_value": 12.5, "proposal_field": "building.proposed_height_m",
            "quote": "the maximum height is restricted to 11.5 meters",
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
                proposed_value=1.5, proposal_field="setbacks.front_m", comparison=">=", status="satisfied",
                derivation="12% * 12")
    rep = verify_findings([finding], PASSAGES, PROPOSAL, ("setbacks",))
    assert rep.passed, rep.errors()
    assert abs(safe_eval("0.12 x 12") - 1.44) < 1e-9
    assert safe_eval("max(1.0, 0.08 * 9)") == 1.0


def test_derivation_written_as_comparison():
    # Real models put the comparison in `derivation`; the evaluable side must equal the
    # required value, and every number on both sides must still be traceable.
    ok = f(derivation="12.5 <= 11.5")
    assert verify_findings([ok], PASSAGES, PROPOSAL, ("height",)).passed
    words = f(derivation="proposed height 12.5 <= 11.5")
    assert verify_findings([words], PASSAGES, PROPOSAL, ("height",)).passed
    invented = f(derivation="12.5 <= 13.0")
    errs = " ".join(verify_findings([invented], PASSAGES, PROPOSAL, ("height",)).errors())
    assert "number_untraceable" in errs


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


def test_revise_when_model_finding_has_no_clause_label():
    # Real models return provision ids only; a violated finding must still route (regression).
    clear = [_ok(t) for t in MANDATORY_TOPICS]
    bare = {"provision_id": "ZR2015:T10:ii.b", "topic": "height", "status": "violated"}
    d = _decide(clear + [bare])
    assert d.route == Route.revise and "ZR2015:T10:ii.b" in d.reason


def test_precedence_supersedes_byelaw_on_governed_topic():
    findings = [_ok(t) for t in MANDATORY_TOPICS] + [_ok("setbacks", "violated", "BBL2003:T5")]
    d = _decide(findings)
    assert d.route == Route.clear and d.superseded == [4]


def test_unresolved_conflict_escalates():
    conflicts = [{"provision_ids": ["BBL2003:s16.0", "BBL2003:T13"], "topic": "parking", "description": "differ"}]
    assert _decide([_ok(t) for t in MANDATORY_TOPICS], conflicts=conflicts).route == Route.specialist


def test_proposed_value_must_match_its_proposal_field():
    # The rear setback compared using a number that is only the side setback (real-model S06 defect).
    prop = {**PROPOSAL, "setbacks": {"front_m": 2.5, "rear_m": 1.5, "left_m": 1.0}}
    wrong = f(provision_id="ZR2015:T8", topic="setbacks", quote="Above 9.0 m 8 % 8% 12% 8 %", required_value=1.44,
              proposed_value=1.0, proposal_field="setbacks.rear_m", comparison=">=", status="violated",
              derivation="8% * 18")
    errs = " ".join(verify_findings([wrong], PASSAGES, prop, ("setbacks",)).errors())
    assert "proposed_value_mismatch" in errs
    unnamed = f(proposal_field=None)
    assert "proposal_field_missing" in " ".join(verify_findings([unnamed], PASSAGES, PROPOSAL, ("height",)).errors())


def test_missing_comparison_operator_fails_verification():
    # VER-001 regression: numeric findings with satisfied/violated status must have a valid comparison operator
    no_cmp = f(comparison=None)
    rep = verify_findings([no_cmp], PASSAGES, PROPOSAL, ("height",))
    assert not rep.passed
    assert "comparison_missing" in " ".join(rep.errors())


def test_short_quote_under_10_chars_fails_verification():
    # VER-002 regression: quotes under 10 chars must not pass as verbatim quotes
    short_quote = f(quote="height")
    rep = verify_findings([short_quote], PASSAGES, PROPOSAL, ("height",))
    assert not rep.passed
    assert "quote_not_in_passage" in " ".join(rep.errors())


def test_derivation_mismatch_counted_as_hallucination():
    # VER-003 regression: derivation mismatches must count toward hallucination
    mismatch = f(required_value=15.0, derivation="12% * 12")
    rep = verify_findings([mismatch], PASSAGES, PROPOSAL, ("height",))
    assert not rep.passed
    assert "derivation_mismatch" in " ".join(rep.errors())
    assert rep.hallucination_rate == 1.0


def test_parse_json_trailing_comma():
    # ROB-001 regression: JSON with trailing commas should be cleanly recovered
    from bpc.agents.runtime import parse_json
    raw_trailing = '```json\n{"status": "satisfied", "count": 42,}\n```'
    parsed = parse_json(raw_trailing)
    assert parsed == {"status": "satisfied", "count": 42}


def test_parse_json_preserves_strings_with_commas_and_braces():
    # ROB-002 regression: parser must not mutate string literals containing commas and braces/brackets
    from bpc.agents.runtime import parse_json
    raw = '''```json
    {
        "clause": "Table 10, note (ii)(b),}",
        "brackets": "sub-clause [ref 4,]",
        "nested": {"key": "val,}"},
        "escaped": "text with \\\"quote,}\\\" and backslash\\\\",
        "array": [1, 2, 3,],
    }
    ```'''
    parsed = parse_json(raw)
    assert parsed is not None
    assert parsed["clause"] == "Table 10, note (ii)(b),}"
    assert parsed["brackets"] == "sub-clause [ref 4,]"
    assert parsed["nested"]["key"] == "val,}"
    assert parsed["escaped"] == 'text with "quote,}" and backslash\\'
    assert parsed["array"] == [1, 2, 3]


def test_parse_json_malformed_returns_none():
    from bpc.agents.runtime import parse_json
    assert parse_json("") is None
    assert parse_json("not json at all") is None
    assert parse_json('{"unclosed": "string') is None
