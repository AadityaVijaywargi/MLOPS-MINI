from bpc.agents.researcher import _needs_selection
from bpc.common.contracts import MANDATORY_TOPICS


def _state(recorded, passages, selected=False):
    return {"recorded": {cid: {"topics": t, "why": []} for cid, t in recorded.items()},
            "passages": {cid: {"chunk_id": cid} for cid in passages}, "selected": selected}


def test_select_runs_when_loop_retrieved_but_recorded_nothing():
    assert _needs_selection(_state({}, ["ZR2015:T10", "ZR2015:T9"]))


def test_select_skipped_when_covered_already_done_or_nothing_retrieved():
    full = {f"ZR2015:x{i}": [t] for i, t in enumerate(MANDATORY_TOPICS)}
    assert not _needs_selection(_state(full, list(full) + ["ZR2015:T9"]))
    assert not _needs_selection(_state({}, ["ZR2015:T10"], selected=True))
    assert not _needs_selection(_state({"ZR2015:T10": ["far"]}, ["ZR2015:T10"]))


def test_select_runs_again_after_a_modifier_round():
    full = {f"ZR2015:x{i}": [t] for i, t in enumerate(MANDATORY_TOPICS)}
    st = _state(full, list(full) + ["ZR2015:T10:ii.b"])
    st["modifier_rounds"] = 1
    assert _needs_selection(st)
