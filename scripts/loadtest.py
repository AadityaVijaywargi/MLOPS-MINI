"""Runs Locust headless at a series of fixed concurrencies and summarises the
full-run latency against the declared SLO (docs/slo.md).

    python scripts/loadtest.py --label base --users 2,4,8,16 --seconds 120
    docker compose up -d --scale researcher=3 --scale assessor=3
    python scripts/loadtest.py --label scaled --users 2,4,8,16 --seconds 120

Each step runs `docker compose --profile loadtest run --rm locust ...` and reads
the CSV it writes to loadtest/results/. The summary goes to
loadtest/results/<label>.md.
"""
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "loadtest" / "results"
SLO_P95_MS = 45_000


def run_step(label: str, users: int, seconds: int, env: dict[str, str]) -> dict:
    prefix = f"{label}_u{users}"
    cmd = ["docker", "compose", "--profile", "loadtest", "run", "--rm"]
    for k, v in env.items():
        cmd += ["-e", f"{k}={v}"]
    cmd += ["locust", "-f", "/mnt/locust/locustfile.py", "--host", "http://api:8000", "--headless",
            "-u", str(users), "-r", str(users), "-t", f"{seconds}s", "--csv", f"/mnt/locust/results/{prefix}",
            "--only-summary"]
    print(">", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=False)
    stats = RESULTS / f"{prefix}_stats.csv"
    row = {"users": users}
    with stats.open() as fh:
        for r in csv.DictReader(fh):
            if r["Type"] == "RUN":
                row.update(runs=int(r["Request Count"]), failures=int(r["Failure Count"]),
                           rps=float(r["Requests/s"]), p50_ms=float(r["50%"]), p95_ms=float(r["95%"]),
                           max_ms=float(r["Max Response Time"]))
            if r["Name"] == "POST /v1/proposals":
                row.update(submit_p95_ms=float(r["95%"]), submit_failures=int(r["Failure Count"]))
    row["slo_met"] = row.get("p95_ms", 1e12) <= SLO_P95_MS and row.get("runs", 0) > 0
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="base")
    ap.add_argument("--users", default="2,4,8,16")
    ap.add_argument("--seconds", type=int, default=120)
    ap.add_argument("--cache-mode", default="miss", choices=["miss", "hit"])
    args = ap.parse_args()
    RESULTS.mkdir(parents=True, exist_ok=True)
    rows = [run_step(args.label, int(u), args.seconds, {"CACHE_MODE": args.cache_mode})
            for u in args.users.split(",")]
    lines = [f"# Load test: {args.label} (cache mode {args.cache_mode}, {args.seconds}s per step)", "",
             f"SLO: p95 submit->result <= {SLO_P95_MS / 1000:.0f} s", "",
             "| users | runs | run/s | p50 s | p95 s | max s | failures | submit p95 ms | SLO met |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['users']} | {r.get('runs')} | {r.get('rps', 0):.2f} | {r.get('p50_ms', 0) / 1000:.1f} | "
                     f"{r.get('p95_ms', 0) / 1000:.1f} | {r.get('max_ms', 0) / 1000:.1f} | {r.get('failures')} | "
                     f"{r.get('submit_p95_ms', 0):.0f} | {'yes' if r['slo_met'] else 'NO'} |")
    text = "\n".join(lines) + "\n"
    (RESULTS / f"{args.label}.md").write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
