from bpc.common.contracts import validate_proposal


def test_valid_reference_case(proposal):
    p, errors = validate_proposal(proposal)
    assert errors == [] and p is not None


def test_schema_errors_are_field_level(proposal):
    proposal["zone"] = "residential"
    proposal["plot"]["width_m"] = -3
    proposal["unexpected"] = 1
    p, errors = validate_proposal(proposal)
    locs = {e.loc for e in errors}
    assert p is None
    assert {"zone", "plot.width_m", "unexpected"} <= locs


def test_cross_field_area_and_setbacks(proposal):
    proposal["plot"]["area_sqm"] = 500
    proposal["setbacks"]["front_m"] = 8
    proposal["setbacks"]["rear_m"] = 6
    p, errors = validate_proposal(proposal)
    locs = {e.loc for e in errors}
    assert p is None and "plot.area_sqm" in locs and "setbacks.front_m" in locs
    assert all(e.type == "cross_field" for e in errors)


def test_far_cannot_exceed_floors_times_coverage(proposal):
    proposal["building"]["proposed_far"] = 3.0
    _, errors = validate_proposal(proposal)
    assert any(e.loc == "building.proposed_far" for e in errors)


def test_multi_dwelling_requires_multi_use(proposal):
    proposal["building"]["dwelling_units"] = 4
    _, errors = validate_proposal(proposal)
    assert any(e.loc == "building.dwelling_units" for e in errors)


def test_non_object_body():
    p, errors = validate_proposal(["not", "an", "object"])
    assert p is None and errors[0].loc == "$"
