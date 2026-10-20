# Load test, scaling and caching results (D6, A7, D7)

Target declared beforehand in `docs/slo.md`: **p95 submit -> final result <= 45 s** at up to
1 run/s, stub LLM at 800-2000 ms per call.

Setup: Docker Desktop on a Windows 11 laptop (8 logical CPUs, 16 GB RAM), whole stack local.
Locust (`loadtest/locustfile.py`) submits a proposal, polls every second until the run is
terminal and records a custom `RUN submit->result` sample (the full run, not the POST). Each
step holds a fixed number of concurrent users for 120 s (`scripts/loadtest.py`); every
proposal is unique (`CACHE_MODE=miss`) so no cache can short-cut a run. A stub run makes
~13 model calls (it never determines, so it always takes the hand-back path) - a heavier run
than a typical real-model run.

Raw CSVs: `loadtest/results/*_stats.csv`; summaries `loadtest/results/*.md`.

## 1. Baseline: 1 researcher + 1 assessor, 4 run slots each (default)

| users | runs done | run/s | p50 s | p95 s | max s | failures | SLO |
|---|---|---|---|---|---|---|---|
| 2 | 11 | 0.09 | 19 | 20 | 20.2 | 0 | met |
| 4 | 20 | 0.17 | 19 | 22 | 22.2 | 0 | met |
| 8 | 24 | 0.20 | 31 | 35 | 37.4 | 0 | met |
| 16 | 16 | 0.13 | 66 | 75 | 74.9 | 0 | **failed** |
| 32 | 12 | 0.10 | 113 | 118 | 117.8 | 0 | **failed** |

**The target fails between 8 and 16 concurrent users** (throughput plateaus at ~0.2 runs/s).
At 16+ users some runs outlive the 120 s step and are not counted, so the true p95 is worse
than shown.

**Component responsible** (Prometheus during the 32-user step): `queue_depth{queue="research",
state="waiting"}` peaked at 33 while `agent_inflight_runs{agent="researcher"}` sat at exactly 4;
the assess queue never had a backlog; retriever search p95 was 18 ms, stub call p95 1.9 s, no
container above 2.5 CPU cores (the retriever, embedding queries) and the agents under 0.4.
The research worker's **run-slot limit** (`WORKER_CONCURRENCY=4` x 1 replica) is the bottleneck:
each slot spends ~95 % of its time waiting on the model.

## 2. `docker compose up --scale researcher=3 --scale assessor=3`

| users | runs done | run/s | p50 s | p95 s | max s | failures | SLO |
|---|---|---|---|---|---|---|---|
| 2 | 11 | 0.09 | 19 | 23 | 23.2 | 0 | met |
| 4 | 22 | 0.18 | 19 | 22 | 22.2 | 0 | met |
| 8 | 45 | 0.38 | 19 | 21 | 22.2 | 0 | met |
| 16 | 78 | 0.65 | 21 | 30 | 31.7 | 0 | met |
| 32 | 65 | 0.54 | 43 | 53 | 53.1 | 0 | **failed** |

Scaling helps: at 16 users p95 drops 75 s -> 30 s and throughput rises 0.13 -> 0.65 runs/s (5x);
the target now fails between 16 and 32 users. But the cause is unchanged: at 32 users the
research queue again peaked at 32 waiting with exactly **12 in flight = 3 replicas x 4 slots**,
and every agent container stayed under 0.4 cores. Scaling worked only because it added slots.

## 3. The actual bottleneck: concurrency, not containers

Same single replica, more slots (`WORKER_CONCURRENCY`):

| config | users | runs done | run/s | p50 s | p95 s | SLO |
|---|---|---|---|---|---|---|
| 1 x 16 slots | 16 | 86 | 0.72 | 19 | 21 | met |
| 1 x 16 slots | 32 | 96 | 0.81 | 31 | 38 | met |
| 1 x 64 slots | 64 (150 s) | 388 | 2.60 | 22 | 25 | met |

One process with 16 slots beats three processes with 4 slots each at 32 users (p95 38 s vs
53 s). At 64 slots / 64 users there is no queueing (research queue waiting = 0, 64 in flight)
and 2.6 runs/s, but the single researcher process reaches **1.0 CPU core** (one Python event loop:
JSON handling, LangGraph state, event writes) and the gateway 0.9 core, and model-step p95 grows
from 2.0 s to 3.2 s because of event-loop contention. That is the next bottleneck, and the point
where `--scale` (more processes) is the right lever.

Why the default stays at 4 slots: with a real free-tier provider the binding limit is the
provider's requests/tokens per minute, long before any of the above. The slot limit doubles as
a cap on concurrent provider calls; raising it only helps when the provider has headroom (paid
tier, or the stub).

## 4. Caching (D7)

Workload: 4 users submitting one of three repeated proposals (`CACHE_MODE=hit`), 120 s.

| configuration | runs | p50 | p95 | billable tokens / run |
|---|---|---|---|---|
| all caches off | 21 | 19 s | 21 s | 31,708 |
| LLM-response + retrieval cache only (run cache off) | 172 | 1.0 s | 1.1 s | 1,375 (96 % of model calls served from cache) |
| all caches on (whole-run cache, warm) | 477 | 19 ms | 34 ms | 0 |

So for a resubmitted identical proposal, caching removes ~96-100 % of model cost and takes p95
from 21 s to ~1 s (LLM cache) or ~34 ms (run cache). For unique proposals (the load test above)
the caches contribute little; retrieval-cache hits mostly save the retriever's CPU. Note the
first LLM-cache measurement showed 0 % hits: see INC-004.

## 5. Cost per run and per 100 runs (L5)

Tokens are recorded per model call at call time and attributed to agent and step
(`run_events`, `llm_tokens_total{agent,step}`, `GET /v1/admin/cost-report`). The stub reports
character-based token estimates and costs $0; the projection below prices those tokens at an
assumed paid rate of $0.10 / 1M input and $0.40 / 1M output tokens (pass your own prices as
query parameters to the cost report).

| | before context compaction (1,100 runs) | after (24 runs) |
|---|---|---|
| research-agent prompt tokens / run | 30,062 | 23,144 (-23 %) |
| total tokens / run | 39,787 | 32,953 (-17 %) |
| model calls / run | ~13 | ~13 |

**Largest single cost driver: `researcher.agent`** (the research loop) - 75 % of all tokens before
compaction, because every turn re-sends the system prompt, the tool schemas and all earlier
tool results. Compaction (older tool results reduced to ids + labels) addressed the growing part;
the remaining per-call overhead is the fixed system prompt + tool schemas.

Projected cost per 100 runs at the assumed rate: **~$0.44** before compaction (cost report,
155 runs), ~$0.36 after. With a free tier the recorded cost is $0; the real constraint is the
free tier's rate limit, which is why runs are rate limited per client and cached.

## 6. Friend 3 Verification Run (`loadtest/results/friend3.md`)

Conducted by Friend 3 (Aarav Yuval B G, SRN: PES1UG24AM004) under the benchmark parameters (`python scripts/loadtest.py --label friend3 --users 2,4,8,16 --seconds 120` with `CACHE_MODE=miss`):

| users | runs done | run/s | p50 s | p95 s | max s | failures | submit p95 ms | SLO met (p95 <= 45s) |
|---|---|---|---|---|---|---|---|---|
| 2 | 8 | 0.07 | 24.0 | 25.0 | 25.2 | 0 | 37 | **yes** |
| 4 | 17 | 0.14 | 23.0 | 25.0 | 25.2 | 0 | 42 | **yes** |
| 8 | 19 | 0.16 | 39.0 | 53.0 | 52.6 | 0 | 60 | **NO** |
| 16 | 16 | 0.13 | 89.0 | 98.0 | 98.2 | 0 | 81 | **NO** |

### Bottleneck Analysis & Findings:
1. **SLO Boundary:** The 45-second end-to-end SLO holds comfortably up to 4 concurrent users (p95 = 25.0 s), but fails at 8 users (p95 = 53.0 s) and deteriorates further at 16 users (p95 = 98.0 s).
2. **Resource vs Concurrency Bottleneck:** Container CPU usage remains well under 0.4 cores throughout the test. Neither CPU, memory, nor retriever search latency (p95 18 ms) constitutes the bottleneck.
3. **Queue Ingestion & Worker Capacity:** Because the default stack runs 1 replica of the research worker with `WORKER_CONCURRENCY=4`, exactly 4 jobs execute concurrently. When 8 or 16 users submit proposals simultaneously, 4 to 12 jobs accumulate in Redis `q:research`.
4. **Conclusion:** The agents are strictly I/O bound waiting on model responses (800–2000 ms per call). As demonstrated in §2 and §3, horizontal scaling (`--scale researcher=3`) or increasing run slots (`WORKER_CONCURRENCY=16`) is the exact architectural lever required to extend SLO compliance beyond 4 concurrent users.
