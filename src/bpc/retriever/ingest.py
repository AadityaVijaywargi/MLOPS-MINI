"""Idempotent corpus pipeline (D2): read -> parse -> chunk -> embed -> index.

    python -m bpc.retriever.ingest                 # incremental: only changed chunks are embedded
    python -m bpc.retriever.ingest --reembed ZR2015  # re-embed one document in place
    python -m bpc.retriever.ingest --rebuild       # drop everything and rebuild

Running it twice on the same corpus is a no-op (0 embedded, 0 deleted). Changed
chunk text is detected by content hash; only those vectors are deleted and
re-added, so re-embedding never requires rebuilding the whole index (L1).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from ..common.config import get_settings
from ..common.observability import get_logger, setup_logging
from .chunking import chunk_document
from .store import EmbeddingCache, index_paths, make_embeddings, read_json

log = get_logger("ingest")


def _parse_pdf(path: Path) -> list[str]:
    from pypdf import PdfReader

    return [page.extract_text() or "" for page in PdfReader(str(path)).pages]


def run(corpus_dir: str, index_dir: str, model: str, reembed: set[str], rebuild: bool) -> dict:
    from langchain_community.vectorstores import FAISS
    from langchain_core.documents import Document

    t0 = time.perf_counter()
    paths = index_paths(index_dir)
    if rebuild and paths["root"].exists():
        for p in ("faiss", "chunks", "state", "meta"):
            target = paths[p]
            shutil.rmtree(target) if target.is_dir() else target.unlink(missing_ok=True)
    paths["root"].mkdir(parents=True, exist_ok=True)

    manifest = yaml.safe_load((Path(corpus_dir) / "manifest.yaml").read_text())
    docs_meta, all_chunks, pages_total = [], [], 0
    for doc in manifest["documents"]:
        pdf = Path(corpus_dir) / doc["file"]
        sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
        pages = _parse_pdf(pdf)
        pages_total += len(pages)
        chunks = chunk_document(doc["doc_id"], doc["short"], doc["title"], pages)
        all_chunks.extend(chunks)
        docs_meta.append({
            "doc_id": doc["doc_id"], "title": doc["title"], "version": doc["version"], "sha256": sha,
            "pages": len(pages), "chunks": len(chunks), "precedence": doc.get("precedence"),
            "governs": doc.get("governs", []), "source_url": doc.get("source_url"),
            "text_layer": sum(1 for p in pages if len(p.strip()) > 50) / max(1, len(pages)),
        })
        log.info("parsed", doc_id=doc["doc_id"], pages=len(pages), chunks=len(chunks))
    t_parse = time.perf_counter()

    state = read_json(paths["state"], {})
    if state.get("embedding_model") not in (None, model):
        log.warning("embedding model changed; full rebuild", old=state.get("embedding_model"), new=model)
        state = {}
        shutil.rmtree(paths["faiss"], ignore_errors=True)
    old_hashes: dict[str, str] = state.get("chunks", {})
    new_hashes = {c.chunk_id: c.content_hash for c in all_chunks}
    to_delete = [cid for cid, h in old_hashes.items() if new_hashes.get(cid) != h]
    to_add = [c for c in all_chunks if old_hashes.get(c.chunk_id) != c.content_hash]
    adding = {c.chunk_id for c in to_add}
    forced = [c for c in all_chunks if c.doc_id in reembed and c.chunk_id not in adding]
    to_delete += [c.chunk_id for c in forced]
    to_add += forced

    embeddings = make_embeddings(model)
    cache = EmbeddingCache(paths["embcache"], model)
    vectors, embedded, reused = [], 0, 0
    pending = [c for c in to_add if c.doc_id in reembed or cache.get(c.content_hash) is None]
    if pending:
        fresh = embeddings.embed_documents([c.embed_text for c in pending])
        for c, v in zip(pending, fresh):
            cache.put(c.content_hash, v)
        cache.commit()
        embedded = len(pending)
    for c in to_add:
        vectors.append(cache.get(c.content_hash))
    reused = len(to_add) - embedded
    t_embed = time.perf_counter()

    store = None
    if paths["faiss"].exists():
        store = FAISS.load_local(str(paths["faiss"]), embeddings, allow_dangerous_deserialization=True)
        live = [cid for cid in to_delete if cid in store.index_to_docstore_id.values()]
        if live:
            store.delete(live)
    if to_add:
        pairs = [(c.embed_text, v) for c, v in zip(to_add, vectors)]
        metas = [{"chunk_id": c.chunk_id, "doc_id": c.doc_id} for c in to_add]
        ids = [c.chunk_id for c in to_add]
        if store is None:
            store = FAISS.from_embeddings(pairs, embeddings, metadatas=metas, ids=ids)
        else:
            store.add_embeddings(pairs, metadatas=metas, ids=ids)
    changed = bool(to_add or to_delete) or not paths["meta"].exists()
    if store is not None and changed:
        store.save_local(str(paths["faiss"]))
        with paths["chunks"].open("w", encoding="utf-8") as fh:
            for c in all_chunks:
                fh.write(json.dumps(c.to_dict(), ensure_ascii=False) + "\n")
        paths["state"].write_text(json.dumps({"embedding_model": model, "chunks": new_hashes}))
    elapsed = time.perf_counter() - t0
    corpus_version = hashlib.sha256("".join(d["sha256"] for d in docs_meta).encode()).hexdigest()[:12]
    meta = read_json(paths["meta"], {})
    if changed:
        meta = {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "built_at_unix": time.time(),
            "index_version": hashlib.sha256(json.dumps(new_hashes, sort_keys=True).encode()).hexdigest()[:12],
            "corpus_version": corpus_version,
            "embedding_model": model,
            "documents": docs_meta,
            "chunk_count": len(all_chunks),
        }
    meta["last_run"] = {
        "at": datetime.now(timezone.utc).isoformat(),
        "changed": changed,
        "embedded": embedded,
        "reused_from_cache": reused,
        "deleted": len(set(to_delete)),
        "pages": pages_total,
        "seconds_total": round(elapsed, 3),
        "seconds_parse": round(t_parse - t0, 3),
        "seconds_embed": round(t_embed - t_parse, 3),
        "pages_per_second": round(pages_total / elapsed, 2),
        "chunks_per_second": round(len(all_chunks) / elapsed, 2),
    }
    paths["meta"].write_text(json.dumps(meta, indent=2))
    log.info("ingest complete", **meta["last_run"], chunk_count=len(all_chunks))
    return meta


def main() -> int:
    setup_logging("indexer")
    s = get_settings()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus-dir", default=s.corpus_dir)
    ap.add_argument("--index-dir", default=s.index_dir)
    ap.add_argument("--reembed", action="append", default=[], help="doc_id to re-embed in place")
    ap.add_argument("--rebuild", action="store_true")
    args = ap.parse_args()
    if not s.embedding_model:
        print("EMBEDDING_MODEL is not set", file=sys.stderr)
        return 2
    meta = run(args.corpus_dir, args.index_dir, s.embedding_model, set(args.reembed), args.rebuild)
    print(json.dumps(meta["last_run"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
