import copy

import pytest

BASE = {
    "schema_version": "1.0", "client_reference": "t-1", "jurisdiction": "BBMP-Bengaluru",
    "zone": "residential_main", "building_use": "residential_single_dwelling",
    "plot": {"area_sqm": 108, "width_m": 9, "depth_m": 12, "is_corner": False, "is_irregular": False, "ring": "III"},
    "road": {"abutting_road_width_m": 6.0},
    "building": {"proposed_height_m": 12.5, "floors_above_ground": 4, "has_stilt": True, "basement_floors": 0,
                 "proposed_far": 1.70, "ground_coverage_pct": 60, "dwelling_units": 1, "car_parking_spaces": 1},
    "setbacks": {"front_m": 1.5, "rear_m": 1.0, "left_m": 1.0, "right_m": 1.0},
    "notes": "Residential house with stilt parking.",
}


@pytest.fixture
def proposal():
    return copy.deepcopy(BASE)
