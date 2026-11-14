"""Dựng index dense cấp unit cho Day 7 trong vector store Day 6.

Cùng embedding model và cùng thư viện Chroma của Day 6; chỉ khác đơn vị văn bản
(111 unit thay vì 184 paragraph chunk) để dense/lexical/hybrid so sánh trên
đúng một bộ chunk. Thời gian embedding được đo và ghi lại.

    python src/build_index.py
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from retrieval.dense import DIMENSIONS, MODEL_NAME, DenseStore, Embedder
from retrieval.registry import CHUNKS_PATH, MODEL_CACHE, STORE_PATH, load_chunks

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "day7" / "index_manifest.json"


def main() -> None:
    chunks = load_chunks(CHUNKS_PATH)
    embedder = Embedder(cache_dir=MODEL_CACHE)
    store = DenseStore(STORE_PATH)
    started = time.perf_counter()
    count = store.build(chunks, embedder)
    elapsed = time.perf_counter() - started
    if count != len(chunks):
        raise RuntimeError(f"index có {count} vector, cần {len(chunks)}")

    manifest = {
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "store": {"path": str(STORE_PATH.relative_to(ROOT)), "collection": store.collection_name, "metric": "cosine"},
        "embedding": {"provider": "fastembed", "model": MODEL_NAME, "dimensions": DIMENSIONS, "normalized": True},
        "chunks": count,
        "chunk_source": str(CHUNKS_PATH.relative_to(ROOT)),
        "timing_seconds": round(elapsed, 2),
        "cost_usd": 0.0,
        "note": "Local fastembed; không gọi API. Cùng model/version với Day 6, đơn vị văn bản là unit Day 7.",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"indexed {count} chunks in {elapsed:.2f}s -> {STORE_PATH.relative_to(ROOT)}")
    print(f"manifest -> {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
