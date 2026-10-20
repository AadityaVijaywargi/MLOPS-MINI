# Running the real-model evaluation as a team

The 22-scenario evaluation is run in three arms on a real model:

| arm | assessor prompt | modifier step | answers |
|---|---|---|---|
| `real_v1` | v1 | on | L2 baseline |
| `real_v2` | v2 | on | L2 variant, and L3 "before" |
| `real_nomod` | v2 | **off** | L3 "after" (the deliberate change) |

A free-tier key allows about 500 requests per model per day, and one run makes 15-30 model calls,
so one person cannot run all three arms in a day. Each teammate runs **all three arms for one slice
of the scenarios**, with their own key on their own machine. Arms 2 and 3 replay the unchanged
research steps from that machine's response cache, so a slice costs about 25-35 requests per
scenario, roughly 200-280 in total - well inside one day's quota. (Splitting by arm instead would
cost each person 400+ requests and lose the cache reuse.) Keeping a scenario's three arms on one
machine also keeps the comparison controlled: same model, same research, only the variable under
test differs.

| teammate | slice | scenarios |
|---|---|---|
| 1 | `1` | S01-S08 (includes the 4.1 reference case) |
| 2 | `2` | S09-S15 (apartments, exemptions, out-of-corpus, injection) |
| 3 | `3` | S16-S22 (mixed/commercial, large plot, boundaries, high-rise) |

## Steps (each teammate)

1. Clone the repo and start the stack - see "Run it" in `README.md`.
2. In your own `.env` (never commit it), set your own key and **exactly the same provider base URL
   and model id as the rest of the team**, so all slices are comparable. The team shares those two
   values privately; they are deliberately not written anywhere in the repository (D4).
   ```
   LLM_PRIMARY_BASE_URL=<agreed base URL>
   LLM_PRIMARY_API_KEY=<your own key>
   LLM_PRIMARY_MODEL=<agreed model id>
   LLM_PRIMARY_MAX_RPM=12
   LLM_MAX_RETRIES=4
   LLM_BACKOFF_BASE_S=3
   ```
   then `docker compose up -d` (recreates the gateway with them).
3. Run your slice (Git Bash on Windows, any shell on macOS/Linux); it takes about an hour:
   ```bash
   scripts/team_eval.sh 1
   ```
4. Commit `eval/results/real_*_part<N>.*` and push.

If the provider runs out of quota or is overloaded, the affected runs are reported as
`provider degraded` - they are **not** counted in any metric (they measure the provider, not the
system). Rerun just those scenarios after the quota resets (midnight US Pacific) and commit the
extra files; `--merge` prefers the usable result:
```bash
scripts/team_eval.sh 1 S05,S07
```

## Combining (one person, after all slices are pushed)

```bash
docker compose --profile tools run --rm --no-deps eval sh -c '
  cd eval/results &&
  for a in real_v1 real_v2 real_nomod; do
    python -m bpc.evaluation.run_eval --out . --scenarios ../scenarios.yaml --merge $a ${a}_part*.json; done &&
  python -m bpc.evaluation.run_eval --out . --compare real_v1.json real_v2.json &&
  python -m bpc.evaluation.run_eval --out . --compare real_v2.json real_nomod.json'
```
This writes `real_v1|real_v2|real_nomod.{json,md}` and the two before/after tables
`compare_real_v1_vs_real_v2.md` (L2) and `compare_real_v2_vs_real_nomod.md` (L3). Merge prints
`rerun needed: --only ...` if any scenario is still missing or degraded.

## Who wrote what

Suggested ownership of the write-up, matching the slices: teammate 1 - the 4.1 reference case,
architecture and incident log; teammate 2 - the L2 prompt-variant analysis; teammate 3 - the L3
before/after analysis, load test and runbook walkthrough. `git log` shows who ran and committed
which results.
