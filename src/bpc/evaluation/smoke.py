"""End-to-end smoke test of the demonstration items, run inside the stack:

    docker compose exec api python -m bpc.evaluation.smoke            # all checks
    docker compose exec api python -m bpc.evaluation.smoke circuit    # one check

Works with the stub (default) or a real provider. The verification and circuit
checks switch the stub's mode, so they only run when the stub is the provider.
"""
from __future__ import annotations

import copy
import json
import sys
import time
import uuid
from pathlib import Path

import httpx
import yaml

API = "http://api:8000"
STUB = "http://llm-stub:8003"
GATEWAY = "http://llm-gateway:8002"
SPEC = yaml.safe_load(Path("/app/eval/scenarios.yaml").read_text())


def proposal(sid: str = "S02", **extra) -> dict:
    sc = next(s for s in SPEC["scenarios"] if s["id"] == sid)

    def merge(b, o):
        out = copy.deepcopy(b)
        for k, v in o.items():
            out[k] = merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
        return out
    p = merge(SPEC["base"], sc["overrides"])
    p["client_reference"] = f"smoke-{sid}-{uuid.uuid4().hex[:6]}"
    p.update(extra)
    return p


def submit(c: httpx.Client, body, client_id: str = "smoke") -> httpx.Response:
    data = body if isinstance(body, str) else json.dumps(body)
    return c.post(f"{API}/v1/proposals", content=data, headers={"Content-Type": "application/json",
                                                                 "X-Client-Id": client_id})


def wait(c: httpx.Client, run_id: str, timeout: float = 300) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = c.get(f"{API}/v1/runs/{run_id}").json()
        if s["status"] in ("completed", "escalated", "failed"):
            return s
        time.sleep(1.5)
    raise TimeoutError(run_id)


def metric(c: httpx.Client, name: str) -> float:
    total = 0.0
    for line in c.get(f"{API}/metrics").text.splitlines():
        if line.startswith(name) and not line.startswith("#"):
            total += float(line.rsplit(" ", 1)[1])
    return total


def stub_mode(c: httpx.Client, mode: str) -> None:
    c.post(f"{STUB}/admin/mode", json={"mode": mode})


def stub_is_primary(c: httpx.Client) -> bool:
    providers = c.get(f"{GATEWAY}/admin/circuit").json()["providers"]
    return bool(providers) and providers[0].get("host") == httpx.URL(STUB).host


def check_valid(c):
    r = submit(c, proposal("S01", options={"prompt_variant": "default", "bypass_cache": True}))
    s = wait(c, r.json()["run_id"])
    res = s["result"]
    trace = c.get(f"{API}/v1/runs/{s['run_id']}/trace").json()
    cites_ok = all(cit["chunk_id"] in trace["passages_retrieved"] for f in res["findings"] for cit in f["citations"])
    return (res["route"] is not None and cites_ok,
            f"route={res['route']} findings={len(res['findings'])} candidates={len(res['candidate_provisions'])} "
            f"llm_calls={trace['totals']['llm_calls']} tool_calls={trace['totals']['tool_calls']} citations_resolve={cites_ok}")


def check_malformed(c):
    before = metric(c, "runs_submitted_total")
    bad = proposal("S02")
    bad["zone"] = "residential"
    bad["setbacks"]["front_m"] = 8
    bad["setbacks"]["rear_m"] = 6
    r = submit(c, bad)
    body = r.json()
    after = metric(c, "runs_submitted_total")
    q = c.get(f"{API}/v1/quarantine?limit=1").json()["items"][0]
    ok = r.status_code == 422 and body["agent_run_started"] is False and after == before and q["id"] == body["quarantine_id"]
    return ok, f"422={r.status_code == 422} quarantine_id={body.get('quarantine_id')} errors={[e['loc'] for e in body['errors']]} runs_submitted {before}->{after}"


def check_injection(c):
    p = proposal("S15")
    s = wait(c, submit(c, p).json()["run_id"])
    res = s["result"]
    return (res["route"] == "specialist-review" and "prompt_injection_suspected" in res["flags"],
            f"route={res['route']} flags={res['flags']} reason={res['reason'][:90]}")


def check_outside(c):
    s = wait(c, submit(c, proposal("S14")).json()["run_id"])
    res = s["result"]
    return res["route"] == "specialist-review" and "outside" in res["reason"].lower(), f"reason={res['reason'][:120]}"


def check_verification(c):
    stub_mode(c, "hallucinate_once")
    try:
        p = proposal("S02", options={"prompt_variant": "default", "bypass_cache": True})
        s = wait(c, submit(c, p).json()["run_id"])
    finally:
        stub_mode(c, "ok")
    trace = c.get(f"{API}/v1/runs/{s['run_id']}/trace").json()
    v = trace["verification"]
    first_errs = v[0]["errors"] if v else []
    ok = bool(v) and v[0]["status"] == "failed" and any("citation_unresolved" in e for e in first_errs) and len(v) >= 2
    fabricated_returned = any(f["provision_id"] == "ZR2015:T99" for f in s["result"]["findings"])
    return ok and not fabricated_returned, (f"verifications={[x['status'] for x in v]} first_errors={first_errs[:2]} "
                                            f"fabricated_returned={fabricated_returned} route={s['result']['route']}")


def check_circuit(c):
    c.post(f"{GATEWAY}/admin/circuit/reset")
    stub_mode(c, "down")
    try:
        p = proposal("S02", options={"prompt_variant": "default", "bypass_cache": True})
        s = wait(c, submit(c, p).json()["run_id"])
        circuit = c.get(f"{GATEWAY}/admin/circuit").json()["providers"][0]
        p2 = proposal("S06", options={"prompt_variant": "default", "bypass_cache": True})
        t0 = time.time()
        s2 = wait(c, submit(c, p2).json()["run_id"])
        fast = time.time() - t0
    finally:
        stub_mode(c, "ok")
        c.post(f"{GATEWAY}/admin/circuit/reset")
    res = s["result"]
    ok = res["degraded"] and res["route"] == "specialist-review" and circuit["state"] == "open" and s2["result"]["degraded"]
    return ok, (f"circuit={circuit['state']} degraded={res['degraded']} candidates={len(res['candidate_provisions'])} "
                f"second run while open took {fast:.1f}s reason={res['reason'][:70]}")


def check_cache(c):
    p = proposal("S06")
    s1 = wait(c, submit(c, p).json()["run_id"])
    r2 = submit(c, p)
    return r2.status_code == 200 and r2.json().get("cached_from") == s1["run_id"], \
        f"second submit HTTP {r2.status_code} cached_from={r2.json().get('cached_from')}"


def check_rate_limit(c):
    cid = "rl-" + uuid.uuid4().hex[:6]
    codes = [submit(c, "{", client_id=cid).status_code for _ in range(22)]
    return codes.count(429) >= 1 and codes[0] == 422, f"codes: {codes.count(422)}x422 then {codes.count(429)}x429"


def check_feedback_cost(c):
    r = submit(c, proposal("S06"))
    run_id = r.json()["run_id"]
    wait(c, run_id)
    fb = c.post(f"{API}/v1/runs/{run_id}/feedback", json={"satisfactory": True, "reason": "smoke test"})
    summary = c.get(f"{API}/v1/feedback/summary").json()
    cost = c.get(f"{API}/v1/admin/cost-report?hours=24&price_in_per_mtok=0.59&price_out_per_mtok=0.79").json()
    return fb.status_code == 201 and summary["total"] >= 1, (
        f"feedback total={summary['total']} cost_per_100_runs(projected)={cost['cost_per_100_runs_usd']} "
        f"largest_driver={(cost['largest_cost_driver'] or {}).get('agent')}.{(cost['largest_cost_driver'] or {}).get('step')}")


CHECKS = {"valid": check_valid, "malformed": check_malformed, "injection": check_injection, "outside": check_outside,
          "verification": check_verification, "circuit": check_circuit, "cache": check_cache,
          "rate_limit": check_rate_limit, "feedback_cost": check_feedback_cost}
STUB_ONLY = {"verification", "circuit"}  # they drive the stub's failure modes


def main() -> int:
    names = sys.argv[1:] or list(CHECKS)
    failed = 0
    with httpx.Client(timeout=30) as c:
        on_stub = stub_is_primary(c)
        for n in names:
            if n in STUB_ONLY and not on_stub:
                print(f"[SKIP] {n:14s}   n/a  needs the stub as the primary provider", flush=True)
                continue
            t0 = time.time()
            try:
                ok, detail = CHECKS[n](c)
            except Exception as exc:  # report and continue
                ok, detail = False, f"error: {exc!r}"
            failed += not ok
            print(f"[{'PASS' if ok else 'FAIL'}] {n:14s} {time.time() - t0:5.1f}s  {detail}", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
