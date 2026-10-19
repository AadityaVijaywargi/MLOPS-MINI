"""Published data contracts (D1/F1). The JSON Schemas in /contracts are generated
from these models by scripts/export_contracts.py and served at /v1/contracts.

Validation happens in two layers at the ingestion boundary, before any agent
run is created:
  1. schema / type / range / category  -> pydantic
  2. cross-field consistency            -> cross_field_errors()
Both produce field-level errors that are written to the quarantine table."""
from __future__ import annotations

import hashlib
import json
import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

CONTRACT_VERSION = "1.0"


# --------------------------------------------------------------------- enums
class Zone(str, Enum):
    residential_main = "residential_main"
    residential_mixed = "residential_mixed"
    commercial_central = "commercial_central"
    commercial_business = "commercial_business"
    mutation_corridor = "mutation_corridor"
    industrial_general = "industrial_general"
    industrial_hitech = "industrial_hitech"
    public_semi_public = "public_semi_public"
    traffic_transportation = "traffic_transportation"
    agricultural = "agricultural"
    other = "other"


class BuildingUse(str, Enum):
    residential_single_dwelling = "residential_single_dwelling"
    residential_multi_dwelling = "residential_multi_dwelling"
    commercial_retail = "commercial_retail"
    commercial_office = "commercial_office"
    hotel_lodging = "hotel_lodging"
    mixed_residential_commercial = "mixed_residential_commercial"
    institutional_educational = "institutional_educational"
    institutional_hospital = "institutional_hospital"
    institutional_assembly = "institutional_assembly"
    industrial = "industrial"
    other = "other"


class Ring(str, Enum):
    I = "I"
    II = "II"
    III = "III"
    unknown = "unknown"


class Category(str, Enum):
    residential = "residential"
    commercial = "commercial"
    mixed_use = "mixed-use"
    institutional = "institutional"
    other = "other"


USE_TO_CATEGORY: dict[BuildingUse, Category] = {
    BuildingUse.residential_single_dwelling: Category.residential,
    BuildingUse.residential_multi_dwelling: Category.residential,
    BuildingUse.commercial_retail: Category.commercial,
    BuildingUse.commercial_office: Category.commercial,
    BuildingUse.hotel_lodging: Category.commercial,
    BuildingUse.mixed_residential_commercial: Category.mixed_use,
    BuildingUse.institutional_educational: Category.institutional,
    BuildingUse.institutional_hospital: Category.institutional,
    BuildingUse.institutional_assembly: Category.institutional,
    BuildingUse.industrial: Category.other,
    BuildingUse.other: Category.other,
}


class Route(str, Enum):
    clear = "clear-for-submission"
    revise = "revise-and-recheck"
    specialist = "specialist-review"


class RunStatus(str, Enum):
    queued = "queued"
    researching = "researching"
    assessing = "assessing"
    completed = "completed"
    escalated = "escalated"
    failed = "failed"


TERMINAL_STATUSES = {RunStatus.completed.value, RunStatus.escalated.value, RunStatus.failed.value}

Topic = Literal[
    "setbacks", "far", "ground_coverage", "height", "use", "parking", "fire_access", "high_rise", "other"
]
MANDATORY_TOPICS: tuple[str, ...] = ("setbacks", "far", "ground_coverage", "height")


# ------------------------------------------------------------------ proposal
class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Plot(_Strict):
    area_sqm: float = Field(..., gt=10, le=200_000, description="Plot area in square metres")
    width_m: float = Field(..., ge=1.5, le=1000, description="Plot width (frontage) in metres")
    depth_m: float = Field(..., ge=1.5, le=1000, description="Plot depth in metres")
    is_corner: bool = Field(False, description="Plot abuts two roads at a corner")
    is_irregular: bool = Field(False, description="Plot is not approximately rectangular")
    ring: Ring = Field(Ring.unknown, description="RMP-2015 ring (I/II/III) the plot lies in")


class Road(_Strict):
    abutting_road_width_m: float = Field(..., ge=1, le=120, description="Width of the abutting public road")
    secondary_road_width_m: float | None = Field(None, ge=1, le=120, description="Second road (corner/through plots)")


class Building(_Strict):
    proposed_height_m: float = Field(..., ge=2, le=300)
    floors_above_ground: int = Field(..., ge=1, le=100, description="Habitable floors above ground, excluding stilt")
    has_stilt: bool = False
    basement_floors: int = Field(0, ge=0, le=5)
    proposed_far: float = Field(..., gt=0, le=20)
    ground_coverage_pct: float = Field(..., gt=0, le=100)
    total_built_up_sqm: float | None = Field(None, gt=0, le=5_000_000)
    dwelling_units: int = Field(1, ge=0, le=5000)
    car_parking_spaces: int = Field(0, ge=0, le=20000)


class Setbacks(_Strict):
    front_m: float = Field(..., ge=0, le=200)
    rear_m: float = Field(..., ge=0, le=200)
    left_m: float = Field(..., ge=0, le=200)
    right_m: float = Field(..., ge=0, le=200)


class RunOptions(_Strict):
    prompt_variant: Literal["default", "v1", "v2"] = "default"
    bypass_cache: bool = False


class Proposal(_Strict):
    schema_version: Literal["1.0"] = "1.0"
    client_reference: str = Field(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    jurisdiction: Literal["BBMP-Bengaluru"] = Field(..., description="Only jurisdictions in the indexed corpus")
    zone: Zone
    building_use: BuildingUse
    plot: Plot
    road: Road
    building: Building
    setbacks: Setbacks
    notes: str = Field("", max_length=2000, description="Free-text notes. Untrusted: screened by guardrails.")
    options: RunOptions = Field(default_factory=RunOptions)

    @field_validator("notes")
    @classmethod
    def _strip_control_chars(cls, v: str) -> str:
        return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", v)

    def canonical_hash(self) -> str:
        data = self.model_dump(mode="json", exclude={"client_reference", "options"})
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


class FieldError(BaseModel):
    loc: str
    msg: str
    type: str
    input: Any = None


def cross_field_errors(p: Proposal) -> list[FieldError]:
    errs: list[FieldError] = []

    def add(loc: str, msg: str, value: Any = None) -> None:
        errs.append(FieldError(loc=loc, msg=msg, type="cross_field", input=value))

    pl, b, s = p.plot, p.building, p.setbacks
    if not pl.is_irregular:
        product = pl.width_m * pl.depth_m
        if abs(product - pl.area_sqm) / pl.area_sqm > 0.10:
            add("plot.area_sqm", f"area {pl.area_sqm} differs from width x depth ({product:.1f}) by more than 10%; "
                "set plot.is_irregular=true for non-rectangular plots", pl.area_sqm)
    if s.front_m + s.rear_m >= pl.depth_m:
        add("setbacks.front_m", "front + rear setbacks must be less than plot depth", s.front_m + s.rear_m)
    if s.left_m + s.right_m >= pl.width_m:
        add("setbacks.left_m", "left + right setbacks must be less than plot width", s.left_m + s.right_m)
    if not pl.is_irregular and s.front_m + s.rear_m < pl.depth_m and s.left_m + s.right_m < pl.width_m:
        envelope = (pl.width_m - s.left_m - s.right_m) * (pl.depth_m - s.front_m - s.rear_m)
        footprint = pl.area_sqm * b.ground_coverage_pct / 100
        if footprint > envelope * 1.05:
            add("building.ground_coverage_pct",
                f"footprint {footprint:.1f} sqm does not fit inside the setback envelope ({envelope:.1f} sqm)",
                b.ground_coverage_pct)
    max_far = b.floors_above_ground * b.ground_coverage_pct / 100
    if b.proposed_far > max_far * 1.02 + 0.01:
        add("building.proposed_far",
            f"FAR {b.proposed_far} exceeds floors x coverage ({max_far:.2f}); not geometrically possible",
            b.proposed_far)
    min_h = 2.4 * b.floors_above_ground
    max_h = 6.0 * b.floors_above_ground + (4.5 if b.has_stilt else 0) + 3.0
    if not (min_h <= b.proposed_height_m <= max_h):
        add("building.proposed_height_m",
            f"height {b.proposed_height_m} m is implausible for {b.floors_above_ground} floor(s) "
            f"(expected {min_h:.1f}-{max_h:.1f} m)", b.proposed_height_m)
    if b.total_built_up_sqm is not None:
        implied = b.proposed_far * pl.area_sqm
        if abs(implied - b.total_built_up_sqm) / b.total_built_up_sqm > 0.05:
            add("building.total_built_up_sqm",
                f"built-up area disagrees with FAR x plot area ({implied:.1f} sqm) by more than 5%",
                b.total_built_up_sqm)
    multi = {BuildingUse.residential_multi_dwelling, BuildingUse.mixed_residential_commercial}
    if b.dwelling_units > 1 and p.building_use not in multi:
        add("building.dwelling_units", "more than one dwelling unit requires building_use "
            "residential_multi_dwelling or mixed_residential_commercial", b.dwelling_units)
    if p.building_use == BuildingUse.residential_multi_dwelling and b.dwelling_units < 2:
        add("building.dwelling_units", "residential_multi_dwelling requires at least 2 dwelling units", b.dwelling_units)
    if p.road.secondary_road_width_m is not None and not pl.is_corner:
        add("road.secondary_road_width_m", "secondary road given but plot.is_corner is false", p.road.secondary_road_width_m)
    return errs


def validate_proposal(raw: Any) -> tuple[Proposal | None, list[FieldError]]:
    if not isinstance(raw, dict):
        return None, [FieldError(loc="$", msg="request body must be a JSON object", type="type_error")]
    try:
        proposal = Proposal.model_validate(raw)
    except ValidationError as exc:
        errors = [
            FieldError(
                loc=".".join(str(x) for x in e["loc"]) or "$",
                msg=e["msg"],
                type=e["type"],
                input=e.get("input") if not isinstance(e.get("input"), (dict, list)) else None,
            )
            for e in exc.errors()
        ]
        return None, errors
    errs = cross_field_errors(proposal)
    return (None, errs) if errs else (proposal, [])


# ------------------------------------------------------------------- results
class Passage(BaseModel):
    chunk_id: str
    doc_id: str
    clause_label: str
    section: str | None = None
    page: int | None = None
    text: str
    score: float | None = None
    dense_score: float | None = None
    lexical_score: float | None = None


class Citation(BaseModel):
    chunk_id: str
    doc_id: str
    clause_label: str
    page: int | None = None
    quote: str
    passage_text: str | None = None


class Finding(BaseModel):
    provision_id: str
    topic: str
    clause_label: str
    requirement: str
    required_value: float | None = None
    proposed_value: float | None = None
    unit: str | None = None
    comparison: str | None = None
    status: Literal["satisfied", "violated", "not_determinable", "not_applicable"]
    explanation: str
    derivation: str | None = None
    citations: list[Citation]
    verified: bool = False


class Escalation(BaseModel):
    required: bool
    reasons: list[str] = []
    path: str = ("Refer to a licensed architect/structural engineer for review before submission "
                 "to the BBMP sanctioning authority.")


class RunResult(BaseModel):
    run_id: str
    status: str
    route: Route | None = None
    reason: str | None = None
    category: str | None = None
    findings: list[Finding] = []
    candidate_provisions: list[Citation] = []
    withheld_findings: int = 0
    escalation: Escalation | None = None
    flags: list[str] = []
    degraded: bool = False
    prompt_versions: dict[str, str] = {}
    cost_usd: float | None = None
    tokens: dict[str, int] = {}
    disclaimer: str = ("Pre-check finding only. This service never certifies a plan as compliant; "
                       "a licensed architect or engineer makes the determination.")


class FeedbackIn(_Strict):
    satisfactory: bool
    reason: str = Field(..., min_length=3, max_length=1000)


class SubmitResponse(BaseModel):
    run_id: str
    status: str
    status_url: str
    trace_url: str
    poll_after_s: float = 2.0
    cached_from: str | None = None


class RejectResponse(BaseModel):
    error: Literal["validation_failed"] = "validation_failed"
    quarantine_id: int
    errors: list[FieldError]
    agent_run_started: Literal[False] = False
