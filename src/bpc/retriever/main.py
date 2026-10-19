"""Retriever service: hybrid (dense FAISS via LangChain + BM25) search over the
structure-aware chunks, clause lookup by id, and cross-reference resolution.

Dense retrieval catches paraphrase ("how tall can I build"); BM25 catches the
exact tokens table rows are made of ("9.0 m", "Table 10", "11.5"). They are
fused with reciprocal-rank fusion."""
from __future__ import annotations

from contextlib import asynccontextmanager

import asyncio
import hashlib
import json
import re
import time
from collections import OrderedDict
from typing import Literal

import numpy as np
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException
from prometheus_client import Counter, Gauge, Histogram
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from ..common.config import get_settings
from ..common.observability import (
    get_logger, install_http_middleware, mark_service_started, setup_logging, setup_tracing, tracer,
)
from .store import index_paths, make_embeddings, read_chunks, read_json

SERVICE = "retriever"
setup_logging(SERVICE)
log = get_logger(SERVICE)
settings = get_settings()

SEARCH_LATENCY = Histogram("retrieval_search_seconds", "Search latency", ["mode", "cache"],
                           buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5))
EMBED_LATENCY = Histogram("retrieval_query_embed_seconds", "Query embedding latency",
                          buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5))
CACHE = Counter("retrieval_cache_total", "Retrieval cache lookups", ["layer", "result"])
INDEX_BUILT = Gauge("index_built_timestamp_seconds", "When the loaded index was built (unix)")
INDEX_CHUNKS = Gauge("index_chunks", "Chunks in the loaded index")
INDEX_DOC = Gauge("index_document_info", "Indexed document versions", ["doc_id", "version", "sha256"])
INDEX_DOC_CHUNKS = Gauge("index_document_chunks", "Chunks per document", ["doc_id"])
PIPE_THROUGHPUT = Gauge("ingest_pipeline_throughput", "Last ingest run throughput", ["unit"])
PIPE_SECONDS = Gauge("ingest_pipeline_seconds", "Last ingest run duration", ["stage"])
PIPE_COUNTS = Gauge("ingest_pipeline_last_run", "Last ingest run counts", ["kind"])

TOKEN = re.compile(r"[a-z]+|\d+(?:\.\d+)?")


def tokenize(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


class Index:
    def __init__(self) -> None:
        self.store = None
        self.chunks: dict[str, dict] = {}
        self.order: list[str] = []
        self.bm25 = None
        self.meta: dict = {}
        self.embeddings = None
        self.qcache: OrderedDict[str, np.ndarray] = OrderedDict()

    @property
    def ready(self) -> bool:
        return self.store is not None

    def load(self) -> None:
        from langchain_community.vectorstores import FAISS
        from rank_bm25 import BM25Okapi

        paths = index_paths(settings.index_dir)
        if not paths["faiss"].exists():
            raise RuntimeError(f"no index at {paths['faiss']}; run the indexer")
        meta = read_json(paths["meta"], {})
        if self.embeddings is None:
            self.embeddings = make_embeddings(meta.get("embedding_model") or settings.embedding_model)
        store = FAISS.load_local(str(paths["faiss"]), self.embeddings, allow_dangerous_deserialization=True)
        rows = read_chunks(paths["chunks"])
        self.chunks = {r["chunk_id"]: r for r in rows}
        self.order = [r["chunk_id"] for r in rows]
        self.bm25 = BM25Okapi([tokenize(r["header"] + " " + r["text"]) for r in rows])
        self.store, self.meta = store, meta
        self.qcache.clear()
        INDEX_BUILT.set(meta.get("built_at_unix", 0))
        INDEX_CHUNKS.set(len(rows))
        for d in meta.get("documents", []):
            INDEX_DOC.labels(d["doc_id"], d["version"], d["sha256"][:12]).set(1)
            INDEX_DOC_CHUNKS.labels(d["doc_id"]).set(d["chunks"])
        lr = meta.get("last_run", {})
        PIPE_THROUGHPUT.labels("pages_per_second").set(lr.get("pages_per_second", 0))
        PIPE_THROUGHPUT.labels("chunks_per_second").set(lr.get("chunks_per_second", 0))
        for stage in ("total", "parse", "embed"):
            PIPE_SECONDS.labels(stage).set(lr.get(f"seconds_{stage}", 0))
        for kind in ("embedded", "reused_from_cache", "deleted"):
            PIPE_COUNTS.labels(kind).set(lr.get(kind, 0))
        log.info("index loaded", chunks=len(rows), version=meta.get("index_version"))

    def embed_query(self, query: str) -> np.ndarray:
        if query in self.qcache:
            self.qcache.move_to_end(query)
            CACHE.labels("query_embedding", "hit").inc()
            return self.qcache[query]
        CACHE.labels("query_embedding", "miss").inc()
        with EMBED_LATENCY.time():
            vec = np.asarray(self.embeddings.embed_query(query), dtype=np.float32)
        self.qcache[query] = vec
        if len(self.qcache) > 2048:
            self.qcache.popitem(last=False)
        return vec

    def search(self, query: str, k: int, mode: str, doc_id: str | None) -> list[dict]:
        fetch = max(30, k * 5)
        dense: dict[str, float] = {}
        lexical: dict[str, float] = {}
        ranks: dict[str, float] = {}
        if mode in ("hybrid", "dense"):
            vec = self.embed_query(query)
            hits = self.store.similarity_search_with_score_by_vector(vec.tolist(), k=fetch)
            rank = 0
            for doc, dist in hits:
                cid = doc.metadata["chunk_id"]
                if doc_id and not cid.startswith(doc_id + ":"):
                    continue
                dense[cid] = float(1 - dist / 2)  # squared L2 on unit vectors -> cosine
                ranks[cid] = ranks.get(cid, 0) + 1 / (60 + rank)
                rank += 1
        if mode in ("hybrid", "lexical"):
            scores = self.bm25.get_scores(tokenize(query))
            top = np.argsort(scores)[::-1][:fetch]
            rank = 0
            for idx in top:
                if scores[idx] <= 0:
                    break
                cid = self.order[idx]
                if doc_id and not cid.startswith(doc_id + ":"):
                    continue
                lexical[cid] = float(scores[idx])
                ranks[cid] = ranks.get(cid, 0) + 1 / (60 + rank)
                rank += 1
        best = sorted(ranks.items(), key=lambda kv: kv[1], reverse=True)[:k]
        return [self.passage(cid, score=s, dense=dense.get(cid), lexical=lexical.get(cid)) for cid, s in best]

    def passage(self, cid: str, score: float | None = None, dense: float | None = None,
                lexical: float | None = None) -> dict:
        c = self.chunks[cid]
        return {
            "chunk_id": cid, "doc_id": c["doc_id"], "clause_label": c["clause_label"],
            "section": c.get("section"), "page": c.get("page_start"), "header": c["header"],
            "text": c["text"], "refs": c.get("refs", []), "neighbors": c.get("neighbors", []),
            "score": round(score, 5) if score is not None else None,
            "dense_score": round(dense, 4) if dense is not None else None,
            "lexical_score": round(lexical, 3) if lexical is not None else None,
        }

    def resolve_reference(self, reference: str, doc_id: str | None) -> list[str]:
        ref = reference.strip()
        docs = [doc_id] if doc_id else ["ZR2015", "BBL2003"]
        m = re.search(r"table\s*\.?\s*(?:no\.?\s*:?\s*)?(\d{1,2})", ref, re.I) or re.match(r"^T(\d{1,2})$", ref)
        prefixes: list[str] = []
        if m:
            prefixes = [f"{d}:T{m.group(1)}" for d in docs]
        else:
            m = re.search(r"(\d{1,2}(?:\.\d{1,2}){1,3})", ref)
            if m:
                if re.search(r"bye\s*-?\s*law", ref, re.I) and not doc_id:
                    docs = ["BBL2003"]
                prefixes = [f"{d}:s{m.group(1)}" for d in docs]
        out = []
        for cid in self.order:
            for p in prefixes:
                rest = cid[len(p):]
                if cid.startswith(p) and (rest == "" or rest[0] in ":~") and "~list" not in cid:
                    out.append(cid)
        return out[:10]


INDEX = Index()
@asynccontextmanager
async def _lifespan(_app):
    await _startup()
    yield


app = FastAPI(title="BPC retriever", version="1.0", lifespan=_lifespan)
install_http_middleware(app, SERVICE)
setup_tracing(SERVICE, app)
_redis: aioredis.Redis | None = None
_lock = asyncio.Lock()


async def _startup() -> None:
    global _redis
    mark_service_started(SERVICE)
    _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        await run_in_threadpool(INDEX.load)
    except Exception as exc:  # health stays red until reload succeeds
        log.error("index load failed", error=str(exc))


class SearchIn(BaseModel):
    query: str = Field(..., min_length=2, max_length=500)
    k: int = Field(6, ge=1, le=20)
    mode: Literal["hybrid", "dense", "lexical"] = "hybrid"
    doc_id: Literal["ZR2015", "BBL2003"] | None = None


class RefIn(BaseModel):
    reference: str = Field(..., min_length=1, max_length=100)
    doc_id: Literal["ZR2015", "BBL2003"] | None = None


@app.get("/health")
async def health():
    if not INDEX.ready:
        raise HTTPException(503, "index not loaded")
    return {"status": "ok", "chunks": len(INDEX.chunks), "index_version": INDEX.meta.get("index_version")}


@app.post("/v1/search")
async def search(body: SearchIn):
    if not INDEX.ready:
        raise HTTPException(503, "index not loaded")
    key = "ret:" + hashlib.sha256(
        json.dumps([INDEX.meta.get("index_version"), body.model_dump()], sort_keys=True).encode()
    ).hexdigest()
    start = time.perf_counter()
    if settings.retrieval_cache_enabled and _redis is not None:
        try:
            cached = await _redis.get(key)
        except Exception:
            cached = None
        if cached:
            CACHE.labels("search", "hit").inc()
            SEARCH_LATENCY.labels(body.mode, "hit").observe(time.perf_counter() - start)
            return {"passages": json.loads(cached), "cached": True, "index_version": INDEX.meta.get("index_version")}
        CACHE.labels("search", "miss").inc()
    with tracer().start_as_current_span("retriever.search") as span:
        span.set_attribute("retrieval.query", body.query)
        span.set_attribute("retrieval.mode", body.mode)
        passages = await run_in_threadpool(INDEX.search, body.query, body.k, body.mode, body.doc_id)
        span.set_attribute("retrieval.results", [p["chunk_id"] for p in passages])
    SEARCH_LATENCY.labels(body.mode, "miss").observe(time.perf_counter() - start)
    if settings.retrieval_cache_enabled and _redis is not None:
        try:
            await _redis.set(key, json.dumps(passages), ex=settings.retrieval_cache_ttl_s)
        except Exception:
            pass
    return {"passages": passages, "cached": False, "index_version": INDEX.meta.get("index_version")}


@app.get("/v1/clause/{chunk_id:path}")
async def clause(chunk_id: str):
    if chunk_id not in INDEX.chunks:
        raise HTTPException(404, f"unknown clause id {chunk_id}")
    p = INDEX.passage(chunk_id)
    p["neighbor_passages"] = [
        {"chunk_id": n, "clause_label": INDEX.chunks[n]["clause_label"], "text": INDEX.chunks[n]["text"][:400]}
        for n in p["neighbors"][:6] if n in INDEX.chunks
    ]
    return p


@app.post("/v1/references")
async def references(body: RefIn):
    ids = INDEX.resolve_reference(body.reference, body.doc_id)
    return {"reference": body.reference, "passages": [INDEX.passage(i) for i in ids]}


@app.get("/v1/meta")
async def meta():
    return INDEX.meta


@app.post("/admin/reload")
async def reload():
    async with _lock:
        await run_in_threadpool(INDEX.load)
    return {"status": "reloaded", "index_version": INDEX.meta.get("index_version")}
