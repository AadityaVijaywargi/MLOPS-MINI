# Service level objective (declared before measurement)

Declared: 2026-10-19, before any load test was run. This file is committed ahead
of `docs/loadtest.md` and was not edited after seeing results.

## Target

**p95 of a complete run - from `POST /v1/proposals` to the moment
`GET /v1/runs/{id}` returns a final result - is at most 45 seconds, at a sustained
arrival of up to 1 run per second, with the model replaced by the stub
(800-2000 ms per call).**

Secondary: availability of the submission endpoint 99.5% (non-5xx) over the test,
and 0 runs returned as a confident answer after a failure.

## Why this number (against section 1 of the brief)

* The thing being avoided is a returned plan: each resubmission to the municipal
  authority costs days to weeks. Against that, any pre-check that finishes inside
  an architect's working session is valuable; one that takes many minutes gets
  skipped. A minute is the practical ceiling for "submit, read the findings,
  adjust a dimension, re-check" to stay interactive.
* The floor is set by the agent design: a run makes about 9 sequential model calls
  (classify, ~5 research turns, modifier check, assessment). At the stub's
  0.8-2.0 s per call the model alone costs ~12 s median and ~18 s at p95. 45 s
  leaves room for retrieval, queueing and one verification retry or hand-back
  without hiding a structural queueing problem.
* 1 run/s (3,600 runs/hour) is far above one office's load; it represents a shared
  service for many offices and is where queueing behaviour becomes visible.

## What is measured

Locust (`loadtest/locustfile.py`) submits, polls every second, and records a custom
`RUN submit->result` sample for the full duration. The p50/p95 of that sample, RPS
and failure counts are reported in `docs/loadtest.md`, stepping concurrency until
the target fails, then repeated with `--scale researcher=3 --scale assessor=3`.
