"""Ghép các thành phần retrieval theo tên phương pháp."""
from __future__ import annotations

import json
from pathlib import Path

from .bm25 import BM25Index
from .dense import DenseRetriever, DenseStore, Embedder
from .dense_day6 import build_day6_retriever
from .hybrid import HybridRetriever

ROOT = Path(__file__).resolve().parents[2]
CHUNKS_PATH = ROOT / "data" / "day6" / "chunks.json"
STORE_PATH = ROOT / "artifacts" / "day7" / "chroma"
MODEL_CACHE = ROOT / "artifacts" / "day6" / "fastembed_cache"

METHODS = ("dense", "dense_day6", "bm25", "hybrid")


def load_chunks(path: Path = CHUNKS_PATH) -> list[dict]:
    chunks = json.loads(path.read_text(encoding="utf-8"))
    if not chunks:
        raise ValueError("chunks.json rỗng")
    return chunks


def build_retriever(method: str, *, chunks: list[dict] | None = None):
    if method not in METHODS:
        raise ValueError(f"method phải là {METHODS}, đang là {method!r}")
    chunks = chunks or load_chunks()
    if method == "bm25":
        return BM25Index(chunks)
    embedder = Embedder(cache_dir=MODEL_CACHE)
    if method == "dense_day6":
        return build_day6_retriever(chunks, embedder)
    store = DenseStore(STORE_PATH)
    dense = DenseRetriever(store, embedder)
    if method == "dense":
        return dense
    return HybridRetriever(dense, BM25Index(chunks))
