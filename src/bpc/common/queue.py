"""A small reliable work queue on Redis lists.

put()  LPUSH q:<name>
get()  BLMOVE q:<name> -> q:<name>:processing, then sets lease:<job_id> with a TTL
ack()  LREM from processing + delete lease
reap() moves jobs whose lease expired (worker crashed mid-job) back to the queue,
       up to max_attempts; returns the ones that exhausted their attempts.
Because LREM returns how many items it removed, only one reaper can win a job."""
from __future__ import annotations

import json
import uuid
from typing import Any

import redis.asyncio as aioredis


class JobQueue:
    def __init__(self, r: aioredis.Redis, name: str, lease_s: int = 60):
        self.r = r
        self.name = name
        self.key = f"q:{name}"
        self.processing = f"q:{name}:processing"
        self.lease_s = lease_s

    async def put(self, job: dict[str, Any]) -> str:
        job.setdefault("job_id", uuid.uuid4().hex)
        job.setdefault("attempt", 1)
        await self.r.lpush(self.key, json.dumps(job))
        return job["job_id"]

    async def get(self, timeout_s: float = 5.0, worker_id: str = "") -> dict[str, Any] | None:
        raw = await self.r.blmove(self.key, self.processing, timeout_s, "RIGHT", "LEFT")
        if raw is None:
            return None
        job = json.loads(raw)
        job["_raw"] = raw
        await self.r.set(f"lease:{job['job_id']}", worker_id or "worker", ex=self.lease_s)
        return job

    async def heartbeat(self, job: dict[str, Any]) -> None:
        await self.r.expire(f"lease:{job['job_id']}", self.lease_s)

    async def ack(self, job: dict[str, Any]) -> None:
        await self.r.lrem(self.processing, 1, job["_raw"])
        await self.r.delete(f"lease:{job['job_id']}")

    async def reap(self, max_attempts: int) -> list[dict[str, Any]]:
        dead: list[dict[str, Any]] = []
        for raw in await self.r.lrange(self.processing, 0, -1):
            job = json.loads(raw)
            if await self.r.exists(f"lease:{job['job_id']}"):
                continue
            if await self.r.lrem(self.processing, 1, raw) != 1:
                continue  # another reaper got it
            if job.get("attempt", 1) < max_attempts:
                job["attempt"] = job.get("attempt", 1) + 1
                await self.r.lpush(self.key, json.dumps(job))
            else:
                dead.append(job)
        return dead

    async def depth(self) -> tuple[int, int]:
        return await self.r.llen(self.key), await self.r.llen(self.processing)
