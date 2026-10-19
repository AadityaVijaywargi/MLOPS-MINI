"""Load test (D6/A7/D7). Measures a *complete run* - submission to final result -
not just the submission call. Run with the stub LLM (the default stack).

Headless, stepped concurrency (finds where the SLO breaks):
  docker compose --profile loadtest run --rm locust -f /mnt/locust/locustfile.py \
      --host http://api:8000 --headless --csv /mnt/locust/results/base -t 9m

Environment knobs:
  CACHE_MODE=miss|hit   miss (default) makes every proposal unique; hit reuses a few
  STEPS="2,4,8,12,16,24" concurrency steps;  STEP_SECONDS=90
"""
from __future__ import annotations

import os
import random
import time
import uuid

from locust import HttpUser, LoadTestShape, between, events, task

BASE = {
    "schema_version": "1.0", "jurisdiction": "BBMP-Bengaluru", "zone": "residential_main",
    "building_use": "residential_single_dwelling",
    "plot": {"area_sqm": 108, "width_m": 9, "depth_m": 12, "is_corner": False, "is_irregular": False, "ring": "III"},
    "road": {"abutting_road_width_m": 6.0},
    "building": {"proposed_height_m": 10.5, "floors_above_ground": 3, "has_stilt": True, "basement_floors": 0,
                 "proposed_far": 1.6, "ground_coverage_pct": 60, "dwelling_units": 1, "car_parking_spaces": 1},
    "setbacks": {"front_m": 1.5, "rear_m": 1.0, "left_m": 1.0, "right_m": 1.0},
    "notes": "Residential house with stilt parking.",
}
CACHE_MODE = os.environ.get("CACHE_MODE", "miss")
STEPS = [int(x) for x in os.environ.get("STEPS", "2,4,8,12,16,24").split(",")]
STEP_SECONDS = int(os.environ.get("STEP_SECONDS", "90"))
RUN_TIMEOUT_S = 300


def proposal() -> dict:
    p = {k: (dict(v) if isinstance(v, dict) else v) for k, v in BASE.items()}
    p["client_reference"] = "lt-" + uuid.uuid4().hex[:8]
    if CACHE_MODE == "miss":
        # unique but valid: vary height and FAR slightly so no cache layer can short-cut the run
        p["building"] = dict(BASE["building"], proposed_height_m=round(random.uniform(9.0, 11.4), 2),
                             proposed_far=round(random.uniform(1.2, 1.7), 3))
    else:
        p["building"] = dict(BASE["building"], proposed_height_m=random.choice([10.0, 10.5, 11.0]))
    return p


class Architect(HttpUser):
    wait_time = between(0.5, 1.5)

    @task
    def full_run(self) -> None:
        start = time.perf_counter()
        with self.client.post("/v1/proposals", json=proposal(), headers={"X-Client-Id": "loadtest"},
                              name="POST /v1/proposals", catch_response=True) as r:
            if r.status_code not in (200, 202):
                r.failure(f"submit {r.status_code}")
                self._record(start, exc=Exception(f"submit {r.status_code}"))
                return
            run_id = r.json()["run_id"]
        while True:
            s = self.client.get(f"/v1/runs/{run_id}", name="GET /v1/runs/[id]")
            if s.status_code == 200 and s.json().get("status") in ("completed", "escalated", "failed"):
                body = s.json()
                failed = body["status"] == "failed"
                self._record(start, exc=Exception(body["result"].get("reason")) if failed else None)
                return
            if time.perf_counter() - start > RUN_TIMEOUT_S:
                self._record(start, exc=Exception("run timeout"))
                return
            time.sleep(1.0)

    def _record(self, start: float, exc: Exception | None) -> None:
        events.request.fire(request_type="RUN", name="submit->result",
                            response_time=(time.perf_counter() - start) * 1000, response_length=0,
                            exception=exc, context={})


if os.environ.get("USE_SHAPE"):  # Locust uses any shape class it finds, so only define it on request
    class Steps(LoadTestShape):
        """Concurrency steps for interactive exploration; each step holds for STEP_SECONDS.
        The reported numbers come from scripts/loadtest.py (one fixed-concurrency run per step)."""

        def tick(self):
            idx = int(self.get_run_time() // STEP_SECONDS)
            if idx >= len(STEPS):
                return None
            return STEPS[idx], STEPS[idx]
