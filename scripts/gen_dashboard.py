"""Generates observability/grafana/dashboards/bpc.json (run after editing panels).

    python scripts/gen_dashboard.py
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "observability" / "grafana" / "dashboards" / "bpc.json"
DS = {"type": "prometheus", "uid": "prom"}
panels: list[dict] = []
_id = [0]
_y = [0]


def row(title: str) -> None:
    _id[0] += 1
    panels.append({"type": "row", "title": title, "id": _id[0], "collapsed": False,
                   "gridPos": {"h": 1, "w": 24, "x": 0, "y": _y[0]}})
    _y[0] += 1


def panel(title: str, exprs: list[tuple[str, str]], x: int, w: int = 8, h: int = 8, kind: str = "timeseries",
          unit: str = "short", desc: str = "", newline: bool = False, extra: dict | None = None) -> None:
    _id[0] += 1
    p = {
        "type": kind, "title": title, "id": _id[0], "datasource": DS, "description": desc,
        "gridPos": {"h": h, "w": w, "x": x, "y": _y[0]},
        "targets": [{"datasource": DS, "expr": e, "legendFormat": leg, "refId": chr(65 + i)}
                    for i, (e, leg) in enumerate(exprs)],
        "fieldConfig": {"defaults": {"unit": unit}, "overrides": []},
        "options": {"legend": {"displayMode": "list", "placement": "bottom"}},
    }
    if extra:
        p.update(extra)
    panels.append(p)
    if x + w >= 24:
        _y[0] += h


row("Service level (all containers)")
panel("Availability (scrape up, 5m avg)", [("avg_over_time(up[5m])", "{{job}} {{instance}}")], 0, unit="percentunit",
      desc="Fraction of successful scrapes per target")
panel("Throughput (HTTP req/s by service)", [('sum(rate(http_requests_total[1m])) by (service)', "{{service}}")], 8,
      unit="reqps")
panel("Error rate (5xx share by service)",
      [('sum(rate(http_requests_total{status=~"5.."}[5m])) by (service) / clamp_min(sum(rate(http_requests_total[5m])) by (service), 1e-9)',
        "{{service}}")], 16, unit="percentunit")
panel("HTTP latency p50 / p95 by service",
      [("histogram_quantile(0.5, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service))", "p50 {{service}}"),
       ("histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service))", "p95 {{service}}")],
      0, w=12, unit="s")
panel("Run end-to-end latency p50 / p95 (submission -> final result)",
      [("histogram_quantile(0.5, sum(rate(run_end_to_end_seconds_bucket[5m])) by (le))", "p50"),
       ("histogram_quantile(0.95, sum(rate(run_end_to_end_seconds_bucket[5m])) by (le))", "p95"),
       ("vector(45)", "SLO p95 target (45 s)")], 12, w=12, unit="s")

row("Runs and ingestion")
panel("Completed runs/s by route", [("sum(rate(run_end_to_end_seconds_count[5m])) by (route)", "{{route}}")], 0,
      unit="reqps")
panel("Queue depth", [("queue_depth", "{{queue}} {{state}}")], 8)
panel("Ingestion boundary rejects & rate limiting",
      [("sum(rate(ingest_rejected_total[5m])) by (reason)", "rejected {{reason}}"),
       ("rate(rate_limited_total[5m])", "rate limited"),
       ("sum(rate(guardrail_input_total[5m])) by (flag)", "guardrail {{flag}}")], 16, unit="reqps")

row("Agents (per agent)")
panel("Task success rate", [
    ('sum(rate(agent_tasks_total{outcome="success"}[15m])) by (agent) / clamp_min(sum(rate(agent_tasks_total[15m])) by (agent), 1e-9)',
     "{{agent}} success"),
    ('sum(rate(agent_tasks_total{outcome=~"escalated|handback|degraded"}[15m])) by (agent, outcome) / ignoring(outcome) group_left clamp_min(sum(rate(agent_tasks_total[15m])) by (agent), 1e-9)',
     "{{agent}} {{outcome}}")], 0, unit="percentunit",
      desc="assessor success = routed with verified findings; escalations are counted separately")
panel("Steps and tool calls per run (p50 / p95)", [
    ("histogram_quantile(0.5, sum(rate(agent_steps_per_run_bucket[15m])) by (le, agent))", "steps p50 {{agent}}"),
    ("histogram_quantile(0.95, sum(rate(agent_steps_per_run_bucket[15m])) by (le, agent))", "steps p95 {{agent}}"),
    ("histogram_quantile(0.5, sum(rate(agent_tool_calls_per_run_bucket[15m])) by (le, agent))", "tool calls p50 {{agent}}"),
    ("histogram_quantile(0.95, sum(rate(agent_tool_calls_per_run_bucket[15m])) by (le, agent))", "tool calls p95 {{agent}}")], 8)
panel("Agent latency per run p50 / p95", [
    ("histogram_quantile(0.5, sum(rate(agent_run_seconds_bucket[5m])) by (le, agent))", "p50 {{agent}}"),
    ("histogram_quantile(0.95, sum(rate(agent_run_seconds_bucket[5m])) by (le, agent))", "p95 {{agent}}")], 16, unit="s")
panel("Per-step latency p95", [
    ("histogram_quantile(0.95, sum(rate(agent_step_seconds_bucket[5m])) by (le, agent, step))", "{{agent}} {{step}}")],
      0, w=12, unit="s")
panel("Retry rate", [("sum(rate(agent_retries_total[5m])) by (agent, kind)", "{{agent}} {{kind}}"),
                     ("sum(rate(llm_retries_total[5m])) by (provider)", "gateway {{provider}}")], 12, w=6, unit="reqps")
panel("Container uptime", [("bpc_container_uptime_seconds", "{{name}}")], 18, w=6, unit="s",
      kind="stat", extra={"options": {"reduceOptions": {"calcs": ["lastNotNull"]}, "textMode": "value_and_name"}})

row("LLM provider")
panel("Circuit breaker state (0 closed, 1 half-open, 2 open)", [("llm_circuit_state", "{{provider}}")], 0)
panel("Cost USD/s by agent & step (at call time)", [("sum(rate(llm_cost_usd_total[5m])) by (agent, step)", "{{agent}} {{step}}")],
      8, unit="currencyUSD")
panel("Tokens/s by agent & step", [("sum(rate(llm_tokens_total[5m])) by (agent, step, kind)", "{{agent}} {{step}} {{kind}}")], 16)
panel("Cache hit ratio", [
    ('sum(rate(llm_cache_total{result="hit"}[5m])) / clamp_min(sum(rate(llm_cache_total[5m])), 1e-9)', "LLM response cache"),
    ('sum(rate(retrieval_cache_total{layer="search",result="hit"}[5m])) / clamp_min(sum(rate(retrieval_cache_total{layer="search"}[5m])), 1e-9)', "retrieval cache"),
    ('sum(rate(runs_submitted_total{cached="true"}[5m])) / clamp_min(sum(rate(runs_submitted_total[5m])), 1e-9)', "whole-run cache")],
      0, w=12, unit="percentunit")
panel("Provider calls by outcome", [("sum(rate(llm_requests_total[5m])) by (provider, outcome)", "{{provider}} {{outcome}}"),
                                    ("sum(rate(llm_unavailable_total[5m])) by (agent)", "degraded {{agent}}")], 12, w=12,
      unit="reqps")

row("Resource utilisation per container")
panel("CPU (cores) per container", [
    ("bpc_container_cpu_cores", "{{service}} ({{name}})")], 0, w=12)
panel("Memory per container", [
    ("bpc_container_memory_bytes", "{{service}} ({{name}})")], 12, w=12, unit="bytes")

row("Data freshness and quality")
panel("Index age / chunks", [("time() - index_built_timestamp_seconds", "index age (s)"), ("index_chunks", "chunks")], 0,
      kind="stat", extra={"options": {"reduceOptions": {"calcs": ["lastNotNull"]}, "textMode": "value_and_name"}})
panel("Ingest pipeline throughput (last run)", [("ingest_pipeline_throughput", "{{unit}}"),
                                                ("ingest_pipeline_last_run", "{{kind}}")], 8)
panel("Online quality of sampled live runs", [("online_quality_score", "{{metric}}")], 16, unit="percentunit")
panel("Feedback", [("sum(increase(feedback_total[1h])) by (satisfactory)", "satisfactory={{satisfactory}}")], 0, w=12)
panel("Runs in last hour by status", [("runs_by_status", "{{status}}")], 12, w=12)

dashboard = {
    "uid": "bpc-main", "title": "Building Plan Pre-Check", "schemaVersion": 39, "version": 1, "editable": True,
    "refresh": "10s", "time": {"from": "now-1h", "to": "now"}, "timezone": "browser", "tags": ["bpc"],
    "panels": panels, "templating": {"list": []}, "annotations": {"list": []},
}
OUT.write_text(json.dumps(dashboard, indent=2))
print(f"wrote {OUT} ({len(panels)} panels)")
