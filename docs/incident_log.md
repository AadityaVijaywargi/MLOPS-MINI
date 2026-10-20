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

---

## INC-004 - LLM response cache never hit for resubmitted proposals (2026-10-19)

**Impact.** Identical proposals submitted again (with the whole-run cache off, or after a
bypass) paid the full model cost every time: 0 % LLM cache hits, ~33k billable tokens per run.

**Detection.** The D7 caching measurement: `llm_hit_ratio = 0` for a workload of three repeated
proposals with the LLM cache enabled.

**Root cause.** The proposal view sent to the models included `client_reference`, which is unique
per submission. The LLM cache key is a hash of the messages, so every prompt was different. (The
whole-run cache was unaffected because its key, `canonical_hash()`, already excluded that field.)

**Fix.** `client_reference` (and `options`) are removed from what the agents send to the model in
both `researcher._proposal_view` and `assessor._proposal_view`; they have no bearing on the
assessment. Re-measured: 96 % of model calls served from cache, p95 21 s -> 1.1 s, billable tokens
per run 32,947 -> 1,375.

**Lesson.** Cache keys must be derived from exactly the inputs that determine the answer; a
request id leaking into a prompt silently defeats any response cache.

---

## INC-005 - Real-model runs degraded: free-tier quota is per model and per day (2026-10-19)

**Impact.** The first runs of the 4.1 reference case against the hosted model ended in
`specialist-review` with "LLM unavailable" instead of a determination. The service did the right
thing (degraded, no fabricated finding), but no real-model evaluation could run.

**Detection.** `llm_requests_total{outcome="error"}` and the gateway log: HTTP 429
`RESOURCE_EXHAUSTED`. First run: the per-minute limit (the research loop issues calls faster than
~10/min). After pacing was added, the second run hit
`GenerateRequestsPerDayPerProjectPerModel-FreeTier`, quota value 20, `retryDelay` ~13 h.

**Diagnosis.** One run makes 10-30 model calls, so a 20-request/day model allows about one run a
day; the 22-scenario evaluation needs several hundred calls per arm. The gateway also treated
429 as a generic error: it retried immediately (burning more quota) and counted each retry as a
breaker failure. Two configuration slips preceded this: the base URL pointed at the provider's web
console (HTML, not JSON - the gateway raised a 500 `JSONDecodeError`), and several model ids were
retired or overloaded (404 / 503).

**Fix.**
- Gateway: per-provider request pacing (`LLM_*_MAX_RPM`, sliding 60 s window); 429 handled as
  `QuotaExceeded` that honours the provider's `retry-after`/`retryDelay` up to
  `LLM_QUOTA_MAX_WAIT_S` and otherwise fails fast to the fallback/degraded path; wait time exported
  as `llm_quota_wait_seconds_total`; a non-JSON or malformed upstream body now returns a 502 that
  names `LLM_*_BASE_URL`; hidden "thinking" tokens (`total_tokens - prompt - completion`) are
  counted as output tokens so cost is not under-reported.
- Configuration: switched the primary to a model with a separate, larger daily quota, verified
  first with a single tool-calling probe request.
- Evaluation: `--reuse-model-cache` lets A/B arms replay the unchanged research loop from the
  model-response cache, so the second arm only pays for the calls that differ.

**Lesson.** Free-tier limits are per model and per day, not just per minute; size the evaluation
against the daily budget before starting, and probe a model id with one request before pointing a
whole run at it.

---

## INC-006 - Every real-model run with a violation crashed in the router (2026-10-19)

**Impact.** Once the model worked, the 4.1 reference case failed with
`assessor failed after 2 attempt(s): 'clause_label'` and was escalated, although the assessor had
correctly found `ZR2015:T10:ii.b` violated and verification had passed.

**Detection.** Eval row S01 `status: failed`; the assessor log carried the structured traceback
(`router.decide`, `KeyError: 'clause_label'`) with the run's correlation id.

**Root cause.** The router named violated clauses with `f["clause_label"]`, a field the model's
findings never contain (they carry `provision_id` only; labels come from the cited passage). The
stub never returns a violated finding, and the unit test's helper always set `clause_label`, so
the path was never exercised before a real model reached it.

**Fix.** The assessor attaches the cited passage's `clause_label` to each verified finding before
routing, and the router falls back to the provision id. Regression test
`test_revise_when_model_finding_has_no_clause_label`. S01 re-run: `revise-and-recheck` citing
ZR2015 Table 10 (ii)(b) and Table 9.

A second defect was found in the same trace: the evaluator scored the *first* verification report,
which here was a hand-back with zero findings, so every quality metric was `null`. It now scores the
first report that contains findings (still the model's raw answer, before self-verification
filters it).

**Lesson.** Test doubles that are more convenient than the real dependency hide contract gaps;
the router's input contract is "verified model findings", and the test fixture should have been
built from that, not from the output schema.

---

## INC-007 - Research loop never committed; verifier rejected comparison derivations (2026-10-20)

**Impact.** On the lighter real model, S01 escalated with "no verified finding for: setbacks,
far, ground_coverage, height; research budget exhausted" even though the gold clauses had been
retrieved (context relevance 1.0).

**Detection.** Trace: two research passes, 25 agent calls, 24 `get_clause` + 14 `search_corpus`
tool calls, **zero** `record_provision` calls; both passes hit the loop bound and handed over an
empty dossier. After that was fixed, the assessor's findings were withheld with
`derivation_unparseable: '1.7 <= 1.75'`.

**Root causes.**
1. The research design assumed the model records provisions as it reads them. This model keeps
   reading and never commits, so the step/tool budget (correctly) stops it with nothing recorded.
2. The verifier's derivation check accepted only arithmetic (`0.08 * 15`), but models routinely
   write the comparison itself as the derivation. It also split on the first `=`, which cut
   `1.7 <= 1.75` to `1.7 <` - so for comparison strings only the left-hand number was checked
   for traceability.

**Fix.**
1. New graph node `select_provisions` (prompt `researcher.select@v1`): if the loop ends -
   finished or out of budget - with a mandatory topic uncovered but passages retrieved, one
   bounded JSON call picks the binding passages *from the retrieved set*; ids outside it are
   rejected, so it cannot introduce a clause nobody read. Clauses the model fetched by id rank
   first among the candidates (they carry no search score and were initially cut off by a
   score-sorted cap - the first version of the step accepted nothing because Tables 9/10 were
   not among the 16 candidates). The step is recorded as a `control` event with accepted and
   rejected ids.
2. `verify.derived_value`: a comparison-form derivation is accepted when one side evaluates to
   the required value; every number on both sides must still be traceable to the passage or
   proposal. Only a standalone `=` is treated as a stated result. Tests:
   `test_derivation_written_as_comparison`, `test_researcher_select.py`.

**Result.** S01: escalated after ~240 s -> `revise-and-recheck` citing ZR2015 Table 10 (ii)(b)
in 33 s with 11 model calls. The model's first answer still put prose in `derivation`;
self-verification rejected it and the retry passed - the raw hallucination rate (0.25) is
measured on that first answer.

**Lesson.** An agent loop needs an explicit commit step when the budget runs out: "the model
will record as it goes" is a property of one model, not of the design.

---

## INC-008 - First full real-model pass: budget escalations, false exemption, wrong proposal value (2026-10-20)

**Impact.** The first full v1 pass (`eval/results/dev/real_v1.*`) routed 10/22 correctly. Apart
from the quota (S16-S22, INC-005), five scenarios escalated with only "research budget exhausted
before completion", and trial reruns showed two wrong answers.

**Findings and fixes.**
1. *Budget.* The loop explored until the hard bound, so the modifier check never ran and the
   router (correctly) refused to clear a proposal whose research was cut short. Free exploration
   now ends at `RESEARCHER_SOFT_BUDGET_FRAC` (0.6) of the step/tool budget; the remainder is kept
   for the commit, modifier and coverage steps. A hard bound hit *after* those steps ran is
   recorded as `truncated`, not `exhausted`. The commit step also runs again after a modifier round,
   so modifier passages the model searched for but did not record are not lost.
2. *False exemption (S02).* The assessor listed "parking exempt from FAR" - a rule in a passage -
   as an exemption signal, and the router escalated. Both assessor prompts now say exemption
   signals are only those the proposal itself invokes (v2 previously said "notes or provisions").
3. *Wrong proposal value (S06).* "Rear setback 1.0 m < 1.44 m: violated" - the rear setback is
   1.5 m; 1.0 m is the side setback. The verifier accepted it because 1.0 occurs in the proposal.
   Findings now name `proposal_field` (e.g. `setbacks.rear_m`) and the verifier requires the
   proposed value to equal that field (`proposed_value_mismatch`).
4. *Bursty 503s* from the free tier opened the breaker within a second; the recommended free-tier
   setting is `LLM_MAX_RETRIES=4`, `LLM_BACKOFF_BASE_S=3`.

**Open.** S06 can still escalate with "no verified finding for: height": on a 12 m road no height
cap applies, and the model does not reliably report the road-width cap as `not_applicable`.

**Lesson.** The evaluation found defects that 22 stub-driven scenarios could not: three of the four
are contract gaps between what the model returns and what the next step assumed.
