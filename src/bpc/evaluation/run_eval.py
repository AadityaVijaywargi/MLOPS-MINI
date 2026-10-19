"""Batch evaluation (L3/L2) against the running service.

    python -m bpc.evaluation.run_eval --label baseline [--variant v2] [--only S01,S02]
    python -m bpc.evaluation.run_eval --compare eval/results/a.json eval/results/b.json

Metrics (all computed from the run trace; "raw" = the assessor's first answer,
before self-verification filtered it, so the numbers measure the model, not the
filter):
  groundedness       cited quotes found verbatim in the cited retrieved passage / citations
  context_relevance  gold clause ids retrieved by the research agent / gold clause ids
  faithfulness       numeric findings whose status agrees with their own values / numeric findings
  hallucination_rate findings with an unresolvable id, a non-verbatim quote or an untraceable
                     number / findings
plus route accuracy and recall of the expected violated clauses.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

import httpx
import yaml

TERMINAL = {"completed", "escalated", "failed"}
METRICS = ("groundedness", "context_relevance", "faithfulness", "hallucination_rate", "route_accuracy",
           "violation_recall")


def deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def _avg(xs: list) -> float | None:
    xs = [x for x in xs if x is not None]
    return round(mean(xs), 4) if xs else None


def run_scenario(client: httpx.Client, sc: dict, base: dict, variant: str, timeout_s: float) -> dict:
    proposal = deep_merge(base, sc.get("overrides", {}))
    proposal["client_reference"] = f"eval-{sc['id']}"
    proposal["options"] = {"prompt_variant": variant, "bypass_cache": True}
    t0 = time.time()
    r = client.post("/v1/proposals", json=proposal, headers={"X-Client-Id": "eval"})
    if r.status_code == 429:
        time.sleep(float(r.json().get("retry_after_s", 5)))
        r = client.post("/v1/proposals", json=proposal, headers={"X-Client-Id": "eval"})
    if r.status_code not in (200, 202):
        return {"id": sc["id"], "error": f"submit failed {r.status_code}: {r.text[:300]}"}
    run_id = r.json()["run_id"]
    while True:
        s = client.get(f"/v1/runs/{run_id}").json()
        if s["status"] in TERMINAL or time.time() - t0 > timeout_s:
            break
        time.sleep(2)
    trace = client.get(f"/v1/runs/{run_id}/trace").json()
    result = s.get("result") or {}
    exp = sc["expected"]
    retrieved = set(trace.get("passages_retrieved", []))
    gold = exp.get("gold", [])
    verifs = trace.get("verification", [])
    first = verifs[0] if verifs else {}
    violated_found = {f["provision_id"] for f in result.get("findings", []) if f["status"] == "violated"}
    exp_viol = exp.get("violated", [])
    return {
        "id": sc["id"], "title": sc["title"], "run_id": run_id, "latency_s": round(time.time() - t0, 1),
        "expected_route": exp["route"], "route": result.get("route"), "status": s["status"],
        "route_correct": result.get("route") == exp["route"],
        "context_relevance": (len(retrieved & set(gold)) / len(gold)) if gold else None,
        "gold_missing": sorted(set(gold) - retrieved),
        "groundedness": first.get("groundedness"),
        "faithfulness": first.get("faithfulness"),
        "hallucination_rate": first.get("hallucination_rate"),
        "verification_attempts": len(verifs),
        "violation_recall": (len(violated_found & set(exp_viol)) / len(exp_viol)) if exp_viol else None,
        "violated_found": sorted(violated_found),
        "withheld": result.get("withheld_findings"),
        "reason": result.get("reason"),
        "cost_usd": trace.get("totals", {}).get("cost_usd"),
        "llm_calls": trace.get("totals", {}).get("llm_calls"),
        "tool_calls": trace.get("totals", {}).get("tool_calls"),
        "prompt_versions": trace.get("prompt_versions"),
    }


def summarise(rows: list[dict]) -> dict:
    ok = [r for r in rows if "error" not in r]
    return {
        "scenarios": len(rows), "errors": len(rows) - len(ok),
        "route_accuracy": _avg([1.0 if r["route_correct"] else 0.0 for r in ok]),
        "groundedness": _avg([r["groundedness"] for r in ok]),
        "context_relevance": _avg([r["context_relevance"] for r in ok]),
        "faithfulness": _avg([r["faithfulness"] for r in ok]),
        "hallucination_rate": _avg([r["hallucination_rate"] for r in ok]),
        "violation_recall": _avg([r["violation_recall"] for r in ok]),
        "mean_latency_s": _avg([r["latency_s"] for r in ok]),
        "mean_cost_usd": _avg([r["cost_usd"] for r in ok]),
        "mean_llm_calls": _avg([r["llm_calls"] for r in ok]),
    }


def markdown(label: str, meta: dict, summary: dict, rows: list[dict]) -> str:
    lines = [f"# Evaluation: {label}", "", f"- run at: {meta['at']}", f"- variant: {meta['variant']}",
             f"- api: {meta['api']}", "", "| metric | value |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in summary.items()]
    lines += ["", "| id | expected | got | ctx rel | grounded | faithful | halluc | viol recall | s |",
              "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if "error" in r:
            lines.append(f"| {r['id']} | error: {r['error'][:60]} | | | | | | | |")
            continue
        lines.append(f"| {r['id']} | {r['expected_route']} | {r['route']}{'' if r['route_correct'] else ' X'} | "
                     f"{r['context_relevance']} | {r['groundedness']} | {r['faithfulness']} | "
                     f"{r['hallucination_rate']} | {r['violation_recall']} | {r['latency_s']} |")
    return "\n".join(lines) + "\n"


def compare(a_path: str, b_path: str) -> str:
    a, b = json.loads(Path(a_path).read_text()), json.loads(Path(b_path).read_text())
    lines = [f"# Before / after: {a['label']} -> {b['label']}", "", "| metric | before | after | delta |", "|---|---|---|---|"]
    for m in METRICS + ("mean_latency_s", "mean_cost_usd", "mean_llm_calls"):
        x, y = a["summary"].get(m), b["summary"].get(m)
        d = round(y - x, 4) if isinstance(x, (int, float)) and isinstance(y, (int, float)) else None
        lines.append(f"| {m} | {x} | {y} | {d} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", default=os.environ.get("API_URL", "http://localhost:8000"))
    ap.add_argument("--scenarios", default="eval/scenarios.yaml")
    ap.add_argument("--variant", default="default", choices=["default", "v1", "v2"])
    ap.add_argument("--label", default="run")
    ap.add_argument("--only", default="", help="comma-separated scenario ids")
    ap.add_argument("--out", default="eval/results")
    ap.add_argument("--timeout", type=float, default=400)
    ap.add_argument("--compare", nargs=2, metavar=("BEFORE_JSON", "AFTER_JSON"))
    args = ap.parse_args()
    if args.compare:
        text = compare(*args.compare)
        print(text)
        out = Path(args.out) / f"compare_{Path(args.compare[0]).stem}_vs_{Path(args.compare[1]).stem}.md"
        out.write_text(text)
        return 0
    spec = yaml.safe_load(Path(args.scenarios).read_text())
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    scenarios = [s for s in spec["scenarios"] if not only or s["id"] in only]
    rows = []
    with httpx.Client(base_url=args.api, timeout=30) as client:
        for sc in scenarios:
            row = run_scenario(client, sc, spec["base"], args.variant, args.timeout)
            rows.append(row)
            print(json.dumps({k: row.get(k) for k in ("id", "expected_route", "route", "context_relevance",
                                                       "groundedness", "hallucination_rate", "latency_s", "error")}),
                  flush=True)
    meta = {"at": datetime.now(timezone.utc).isoformat(), "variant": args.variant, "api": args.api}
    summary = summarise(rows)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{args.label}.json").write_text(json.dumps({"label": args.label, **meta, "summary": summary,
                                                             "rows": rows}, indent=2))
    md = markdown(args.label, meta, summary, rows)
    (out_dir / f"{args.label}.md").write_text(md)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
