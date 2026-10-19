"""Index storage shared by the indexer (writer) and the retriever (reader).

Layout of INDEX_DIR:
  faiss/            LangChain FAISS vector store (docstore ids == chunk ids)
  chunks.jsonl      chunk records (text + structure metadata) -> BM25 + clause lookup
  state.json        chunk_id -> content_hash, embedding model (drives incremental updates)
  meta.json         data freshness: build time, document versions/sha256, counts, throughput
  embcache.sqlite   content_hash -> vector, so unchanged text is never re-embedded
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import numpy as np


def index_paths(index_dir: str) -> dict[str, Path]:
    root = Path(index_dir)
    return {
        "root": root,
        "faiss": root / "faiss",
        "chunks": root / "chunks.jsonl",
        "state": root / "state.json",
        "meta": root / "meta.json",
        "embcache": root / "embcache.sqlite",
    }


def make_embeddings(model_name: str):
    from langchain_huggingface import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(model_name=model_name, encode_kwargs={"normalize_embeddings": True})


class EmbeddingCache:
    def __init__(self, path: Path, model: str):
        self.conn = sqlite3.connect(path)
        self.model = model
        self.conn.execute("CREATE TABLE IF NOT EXISTS emb (model TEXT, hash TEXT, vec BLOB, PRIMARY KEY (model, hash))")

    def get(self, h: str) -> list[float] | None:
        row = self.conn.execute("SELECT vec FROM emb WHERE model=? AND hash=?", (self.model, h)).fetchone()
        return np.frombuffer(row[0], dtype=np.float32).tolist() if row else None

    def put(self, h: str, vec: list[float]) -> None:
        self.conn.execute("INSERT OR REPLACE INTO emb VALUES (?,?,?)",
                          (self.model, h, np.asarray(vec, dtype=np.float32).tobytes()))

    def commit(self) -> None:
        self.conn.commit()


def read_json(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def read_chunks(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
