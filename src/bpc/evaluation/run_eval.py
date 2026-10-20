"""Batch evaluation (L3/L2) against the running service.

    python -m bpc.evaluation.run_eval --label baseline [--variant v2] [--only S01,S02]
    python -m bpc.evaluation.run_eval --compare eval/results/a.json eval/results/b.json
    python -m bpc.evaluation.run_eval --merge real_v1 eval/results/real_v1_part*.json

Runs that degraded because the model provider was unavailable (quota, outage) are
flagged `provider_degraded` and left out of every quality metric: they measure the
provider, not the system. `--merge` combines partial runs (e.g. one slice of the
scenarios per teammate, or a rerun of degraded scenarios the next day); for a scenario
present in several files, a usable row wins over a degraded or errored one, else the
later file wins.

Metrics (all computed from the run trace; "raw" = the assessor's first answer
that contains findings, before self-verification filtered it, so the numbers
measure the model, not the filter):
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


def run_scenario(client: httpx.Client, sc: dict, base: dict, variant: str, timeout_s: float,
                 reuse_model_cache: bool = False) -> dict:
    proposal = deep_merge(base, sc.get("overrides", {}))
    proposal["client_reference"] = f"eval-{sc['id']}"
    proposal["options"] = {"prompt_variant": variant, "bypass_cache": True, "reuse_model_cache": reuse_model_cache}
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
    # A report with no findings is a hand-back for missing topics, not an answer to score.
    first = next((v for v in verifs if v.get("total_findings")), {})
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
        "provider_degraded": bool(result.get("degraded")),
        "reason": result.get("reason"),
        "cost_usd": trace.get("totals", {}).get("cost_usd"),
        "llm_calls": trace.get("totals", {}).get("llm_calls"),
        "tool_calls": trace.get("totals", {}).get("tool_calls"),
        "prompt_versions": trace.get("prompt_versions"),
    }


def summarise(rows: list[dict]) -> dict:
    ok = [r for r in rows if "error" not in r and not r.get("provider_degraded")]
    return {
        "scenarios": len(rows), "errors": sum(1 for r in rows if "error" in r),
        "provider_degraded": sum(1 for r in rows if r.get("provider_degraded")), "scored": len(ok),
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
             f"- api: {meta['api']}"]
    if meta.get("merged_from"):
        lines.append(f"- merged from: {', '.join(meta['merged_from'])}")
    lines += ["", "| metric | value |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in summary.items()]
    lines += ["", "| id | expected | got | ctx rel | grounded | faithful | halluc | viol recall | s |",
              "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if "error" in r:
            lines.append(f"| {r['id']} | error: {r['error'][:60]} | | | | | | | |")
            continue
        got = f"{r['route']} (provider down, not scored)" if r.get("provider_degraded") else             f"{r['route']}{'' if r['route_correct'] else ' X'}"
        lines.append(f"| {r['id']} | {r['expected_route']} | {got} | "
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


def _usable(row: dict) -> bool:
    return "error" not in row and not row.get("provider_degraded")


def merge(label: str, paths: list[str], scenarios_path: str) -> dict:
    order = [s["id"] for s in yaml.safe_load(Path(scenarios_path).read_text())["scenarios"]]
    parts = [json.loads(Path(p).read_text()) for p in paths]
    variants = {p["variant"] for p in parts}
    if len(variants) > 1:
        raise SystemExit(f"refusing to merge different prompt variants: {sorted(variants)}")
    best: dict[str, dict] = {}
    for part in parts:
        for row in part["rows"]:
            prev = best.get(row["id"])
            if prev is None or _usable(row) or not _usable(prev):
                best[row["id"]] = row
    rows = sorted(best.values(), key=lambda r: order.index(r["id"]) if r["id"] in order else len(order))
    return {"label": label, "at": datetime.now(timezone.utc).isoformat(), "variant": variants.pop(),
            "api": "merged", "merged_from": [Path(p).name for p in paths], "summary": summarise(rows), "rows": rows}


def _write(out_dir: Path, label: str, doc: dict) -> str:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{label}.json").write_text(json.dumps(doc, indent=2))
    md = markdown(label, doc, doc["summary"], doc["rows"])
    (out_dir / f"{label}.md").write_text(md)
    return md


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", default=os.environ.get("API_URL", "http://localhost:8000"))
    ap.add_argument("--scenarios", default="eval/scenarios.yaml")
    ap.add_argument("--variant", default="default", choices=["default", "v1", "v2"])
    ap.add_argument("--label", default="run")
    ap.add_argument("--only", default="", help="comma-separated scenario ids")
    ap.add_argument("--out", default="eval/results")
    ap.add_argument("--timeout", type=float, default=400)
    ap.add_argument("--reuse-model-cache", action="store_true",
                    help="replay cached model responses for unchanged steps (controlled A/B, saves quota)")
    ap.add_argument("--compare", nargs=2, metavar=("BEFORE_JSON", "AFTER_JSON"))
    ap.add_argument("--merge", nargs="+", metavar=("LABEL", "PART_JSON"),
                    help="combine partial result files into LABEL.json")
    args = ap.parse_args()
    if args.merge:
        if len(args.merge) < 2:
            ap.error("--merge needs a label and at least one part file")
        doc = merge(args.merge[0], args.merge[1:], args.scenarios)
        print(_write(Path(args.out), args.merge[0], doc))
        degraded = [r["id"] for r in doc["rows"] if not _usable(r)]
        missing = [s["id"] for s in yaml.safe_load(Path(args.scenarios).read_text())["scenarios"]
                   if s["id"] not in {r["id"] for r in doc["rows"]}]
        if degraded or missing:
            print(f"rerun needed: --only {','.join(degraded + missing)}")
        return 0
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
            row = run_scenario(client, sc, spec["base"], args.variant, args.timeout, args.reuse_model_cache)
            rows.append(row)
            print(json.dumps({k: row.get(k) for k in ("id", "expected_route", "route", "context_relevance",
                                                       "groundedness", "hallucination_rate", "latency_s", "error")}),
                  flush=True)
    meta = {"at": datetime.now(timezone.utc).isoformat(), "variant": args.variant, "api": args.api,
            "reuse_model_cache": args.reuse_model_cache}
    print(_write(Path(args.out), args.label, {"label": args.label, **meta, "summary": summarise(rows), "rows": rows}))
    degraded = [r["id"] for r in rows if not _usable(r)]
    if degraded:
        print(f"provider degraded or errored (rerun later and --merge): --only {','.join(degraded)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
