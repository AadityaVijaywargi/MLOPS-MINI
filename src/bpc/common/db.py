"""Postgres persistence: runs, per-step events (the run reconstruction log),
quarantine, feedback and quality scores."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

import asyncpg

from .config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id          TEXT PRIMARY KEY,
    client_id       TEXT NOT NULL,
    correlation_id  TEXT NOT NULL,
    proposal_hash   TEXT NOT NULL,
    cache_key       TEXT,
    proposal        JSONB NOT NULL,
    status          TEXT NOT NULL,
    route           TEXT,
    reason          TEXT,
    category        TEXT,
    result          JSONB,
    dossier         JSONB,
    flags           JSONB NOT NULL DEFAULT '[]',
    prompt_versions JSONB NOT NULL DEFAULT '{}',
    degraded        BOOLEAN NOT NULL DEFAULT FALSE,
    trace_id        TEXT,
    cached_from     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS runs_cache_key ON runs (cache_key, finished_at);
CREATE INDEX IF NOT EXISTS runs_status ON runs (status, created_at);

CREATE TABLE IF NOT EXISTS run_events (
    id                BIGSERIAL PRIMARY KEY,
    run_id            TEXT NOT NULL,
    ts                TIMESTAMPTZ NOT NULL DEFAULT now(),
    agent             TEXT NOT NULL,
    step              TEXT NOT NULL,
    kind              TEXT NOT NULL,
    name              TEXT,
    status            TEXT,
    latency_ms        DOUBLE PRECISION,
    prompt_version    TEXT,
    prompt_tokens     INTEGER,
    completion_tokens INTEGER,
    cost_usd          DOUBLE PRECISION,
    payload           JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS run_events_run ON run_events (run_id, id);

CREATE TABLE IF NOT EXISTS quarantine (
    id          BIGSERIAL PRIMARY KEY,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    client_id   TEXT,
    correlation_id TEXT,
    reason      TEXT NOT NULL,
    raw_body    TEXT,
    errors      JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS feedback (
    id           BIGSERIAL PRIMARY KEY,
    run_id       TEXT NOT NULL REFERENCES runs(run_id),
    client_id    TEXT,
    satisfactory BOOLEAN NOT NULL,
    reason       TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS quality_scores (
    id                 BIGSERIAL PRIMARY KEY,
    run_id             TEXT NOT NULL,
    source             TEXT NOT NULL,
    scored_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    groundedness       DOUBLE PRECISION,
    context_relevance  DOUBLE PRECISION,
    faithfulness       DOUBLE PRECISION,
    hallucination_rate DOUBLE PRECISION,
    details            JSONB NOT NULL DEFAULT '{}'
);
"""


async def _init_conn(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")
    await conn.set_type_codec("json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


async def create_pool(retries: int = 30) -> asyncpg.Pool:
    dsn = get_settings().database_dsn
    last: Exception | None = None
    for _ in range(retries):
        try:
            return await asyncpg.create_pool(dsn, min_size=1, max_size=10, init=_init_conn)
        except (OSError, asyncpg.PostgresError) as exc:
            last = exc
            await asyncio.sleep(2)
    raise RuntimeError(f"database unavailable: {last}")


async def migrate(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock(424242)")
            await conn.execute(SCHEMA)


def now() -> datetime:
    return datetime.now(timezone.utc)


async def record_event(
    pool: asyncpg.Pool,
    run_id: str,
    agent: str,
    step: str,
    kind: str,
    name: str | None = None,
    status: str | None = "ok",
    latency_ms: float | None = None,
    payload: dict[str, Any] | None = None,
    prompt_version: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    cost_usd: float | None = None,
) -> None:
    await pool.execute(
        """INSERT INTO run_events (run_id, agent, step, kind, name, status, latency_ms, prompt_version,
               prompt_tokens, completion_tokens, cost_usd, payload)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)""",
        run_id, agent, step, kind, name, status, latency_ms, prompt_version,
        prompt_tokens, completion_tokens, cost_usd, payload or {},
    )


async def update_run(pool: asyncpg.Pool, run_id: str, **fields: Any) -> None:
    if not fields:
        return
    cols = list(fields)
    sets = ", ".join(f"{c} = ${i + 2}" for i, c in enumerate(cols))
    await pool.execute(
        f"UPDATE runs SET {sets}, updated_at = now() WHERE run_id = $1", run_id, *[fields[c] for c in cols]
    )


async def get_run(pool: asyncpg.Pool, run_id: str) -> dict[str, Any] | None:
    row = await pool.fetchrow("SELECT * FROM runs WHERE run_id = $1", run_id)
    return dict(row) if row else None


async def run_cost(pool: asyncpg.Pool, run_id: str) -> tuple[float, int, int]:
    row = await pool.fetchrow(
        """SELECT COALESCE(SUM(cost_usd),0) AS cost, COALESCE(SUM(prompt_tokens),0) AS pt,
                  COALESCE(SUM(completion_tokens),0) AS ct FROM run_events WHERE run_id = $1""",
        run_id,
    )
    return float(row["cost"]), int(row["pt"]), int(row["ct"])
