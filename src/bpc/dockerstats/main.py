"""Per-container resource exporter (D5/A6): CPU, memory, uptime and restart count
for every container in this compose project, read from the Docker Engine API.

Replaces cAdvisor, which cannot attribute cgroups to containers on Docker Desktop's
containerd image store ("failed to identify the read-write layer ID"). Needs the
Docker socket mounted; it only issues GET requests."""
from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime

import httpx
from prometheus_client import Gauge, start_http_server

PROJECT = os.environ.get("COMPOSE_PROJECT", "bpc")
SOCKET = os.environ.get("DOCKER_SOCKET", "/var/run/docker.sock")
INTERVAL_S = float(os.environ.get("SCRAPE_INTERVAL_S", "10"))
LABELS = ["name", "service"]

CPU = Gauge("bpc_container_cpu_cores", "CPU cores used by the container", LABELS)
MEM = Gauge("bpc_container_memory_bytes", "Memory in use (excluding page cache)", LABELS)
MEM_LIMIT = Gauge("bpc_container_memory_limit_bytes", "Memory limit", LABELS)
UPTIME = Gauge("bpc_container_uptime_seconds", "Seconds since the container started", LABELS)
RESTARTS = Gauge("bpc_container_restarts", "Docker restart count", LABELS)
RUNNING = Gauge("bpc_container_running", "1 if running", LABELS)
NET_RX = Gauge("bpc_container_network_rx_bytes", "Network bytes received", LABELS)
NET_TX = Gauge("bpc_container_network_tx_bytes", "Network bytes sent", LABELS)


def _started(ts: str) -> float:
    ts = ts.split(".")[0].rstrip("Z")
    return datetime.fromisoformat(ts + "+00:00").timestamp()


async def collect(client: httpx.AsyncClient, c: dict) -> None:
    name = c["Names"][0].lstrip("/")
    service = c["Labels"].get("com.docker.compose.service", name)
    lbl = (name, service)
    try:
        stats, inspect = await asyncio.gather(
            client.get(f"/containers/{c['Id']}/stats", params={"stream": "false"}),
            client.get(f"/containers/{c['Id']}/json"))
        s, i = stats.json(), inspect.json()
    except Exception:
        return
    cpu, pre = s.get("cpu_stats", {}), s.get("precpu_stats", {})
    cpu_delta = cpu.get("cpu_usage", {}).get("total_usage", 0) - pre.get("cpu_usage", {}).get("total_usage", 0)
    sys_delta = cpu.get("system_cpu_usage", 0) - pre.get("system_cpu_usage", 0)
    online = cpu.get("online_cpus") or 1
    CPU.labels(*lbl).set((cpu_delta / sys_delta) * online if sys_delta > 0 else 0)
    mem = s.get("memory_stats", {})
    cache = mem.get("stats", {}).get("inactive_file", 0)
    MEM.labels(*lbl).set(max(0, mem.get("usage", 0) - cache))
    MEM_LIMIT.labels(*lbl).set(mem.get("limit", 0))
    state = i.get("State", {})
    RUNNING.labels(*lbl).set(1 if state.get("Running") else 0)
    if state.get("Running") and state.get("StartedAt"):
        UPTIME.labels(*lbl).set(time.time() - _started(state["StartedAt"]))
    RESTARTS.labels(*lbl).set(i.get("RestartCount", 0))
    nets = s.get("networks", {}) or {}
    NET_RX.labels(*lbl).set(sum(n.get("rx_bytes", 0) for n in nets.values()))
    NET_TX.labels(*lbl).set(sum(n.get("tx_bytes", 0) for n in nets.values()))


async def loop() -> None:
    transport = httpx.AsyncHTTPTransport(uds=SOCKET)
    async with httpx.AsyncClient(transport=transport, base_url="http://docker", timeout=15) as client:
        while True:
            try:
                r = await client.get("/containers/json", params={
                    "filters": f'{{"label":["com.docker.compose.project={PROJECT}"]}}'})
                await asyncio.gather(*(collect(client, c) for c in r.json()))
            except Exception as exc:
                print(f"collect failed: {exc}", flush=True)
            await asyncio.sleep(INTERVAL_S)


def main() -> None:
    start_http_server(int(os.environ.get("METRICS_PORT", "9101")))
    asyncio.run(loop())


if __name__ == "__main__":
    main()
