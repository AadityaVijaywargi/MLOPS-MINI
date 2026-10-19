# Incident log

Real failures met while building and running this system, newest last.
Format: what was seen, how it was confirmed, root cause, fix, and what changed so
it does not recur.

---

## INC-001 - Docker engine would not start: orphaned AF_UNIX socket files (2026-10-19)

**Impact.** The whole stack was down for about 15 minutes: `docker compose build` failed
with `failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine`, and
`docker version` hung.

**Detection.** The background build exited at once; `wsl -l -v` showed the
`docker-desktop` distro `Stopped` although Docker Desktop processes were running.

**Diagnosis.** `%LOCALAPPDATA%\Docker\log\host\com.docker.backend.exe.log`:
```
backend cancelling with error: starting services: initializing Inference manager:
listening on unix://C:/Users/<user>/AppData/Local/Docker/run/dockerInference:
remove .../dockerInference: The file cannot be accessed by the system.
```
The file was a 0-byte reparse point (an AF_UNIX socket) left by an earlier Docker session
four days before. Windows refused to delete it (`del`, `Remove-Item`, `fsutil reparsepoint
delete` and `rm` all failed with error 1920). A folder `run.stale-20261015` showed the same
thing had happened before.

**Root cause.** Docker Desktop's backend removes and re-creates its Unix sockets at
start-up; an unclean shutdown left socket files that Windows can no longer open, so the
removal fails and the backend aborts. Fixing the first socket exposed a second one
(`%LOCALAPPDATA%\docker-secrets-engine\engine.sock`) on the next start.

**Fix.** Quit Docker Desktop, *rename* the directories holding the orphaned sockets
(`Docker\run` -> `run.stale-<time>`, `docker-secrets-engine` -> `docker-secrets-engine.stale-<time>`;
renaming a directory works where deleting the socket does not), start Docker Desktop again.
The engine came up (29.6.2) and recreated both directories.

**Follow-up.** Added to the README troubleshooting section; the stale folders can be
deleted after a reboot. Lesson for the runbook mindset: read the backend log first, the
CLI error ("cannot find the file") pointed at the wrong layer.

---

## INC-002 - Circuit breaker never opened during a provider outage (2026-10-19)

**Impact.** With the provider down, every run degraded correctly to `specialist-review`, but
each one still paid the full retry budget (3 attempts with backoff) because the breaker stayed
`closed`; the demo of "circuit opens" failed.

**Detection.** Smoke check `circuit` failed: `circuit=closed degraded=True`.

**Root cause.** The breaker counted one failure per *request* (after retries). The research agent
degrades on the first failed model call, so a run contributes exactly one request failure and the
threshold of 3 was only reached on the third failed run.

**Fix.** `gateway/main.py::_call_with_retry` records every failed *attempt* against the breaker and
stops retrying as soon as the breaker opens. Now the first outage run opens the circuit (3 failed
attempts) and the next run is rejected by the open circuit and degrades in ~1.5 s instead of ~4 s.
Covered by the smoke check `circuit`.

---

## INC-003 - No per-container resource metrics on Docker Desktop (2026-10-19)

**Impact.** The Grafana "resource utilisation per container" panels were empty.

**Detection.** `count(container_memory_working_set_bytes{name=~"bpc-.+"})` returned nothing; only
the root cgroup series existed.

**Diagnosis.** cAdvisor logs: `Failed to create existing container: /docker/<id>: failed to identify
the read-write layer ID`. Giving it the host cgroup namespace (`cgroup: host`) made the cgroups
visible but not attributable; upgrading v0.49.1 -> v0.53.0 did not help. Docker Desktop uses the
containerd image store, whose layer layout cAdvisor cannot map to containers.

**Fix.** Replaced cAdvisor with `docker-stats` (`src/bpc/dockerstats/main.py`), a 90-line exporter
that reads `/containers/{id}/stats` and `/containers/{id}/json` from the Docker API and exports CPU
cores, memory, uptime, restarts and network bytes per compose service. Works on Docker Desktop and
on Linux hosts alike.
