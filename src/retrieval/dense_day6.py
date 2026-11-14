"""Ablation: dense trên collection Day 6 (republic_B_384) rồi gộp về unit.

Giả thuyết: dense trên 111 unit kém vì bge-small-en-v1.5 chỉ nhận 512 token, trong
khi unit Day 6 dài 1.500-4.800 ký tự nên phần lớn văn bản không được embedding.
Collection B của Day 6 chia nhỏ theo paragraph (<= 1.736 ký tự) nên nằm trong
giới hạn token; gộp theo unit (lấy cosine lớn nhất trong các paragraph của unit)
sẽ tăng recall mà vẫn trả về đơn vị văn bản của Day 7.

Đây là ablation về granularity, không phải index mới: cùng vector store Day 6,
cùng embedding model, cùng metric cosine.
"""
from __future__ import annotations

from pathlib import Path

from .dense import DAY6_COLLECTION, DenseStore, Embedder

ROOT = Path(__file__).resolve().parents[2]
DAY6_STORE = ROOT / "artifacts" / "day6" / "chroma"


class DenseDay6BRetriever:
    method = "dense_day6"

    def __init__(self, store: DenseStore, embedder: Embedder, units: list[dict], *, pool_depth: int = 40) -> None:
        self.store = store
        self.embedder = embedder
        self.units = {unit["id"]: unit for unit in units}
        self.pool_depth = pool_depth

    def search(self, query: str, *, top_k: int = 3, filters: dict | None = None) -> list[dict]:
        vector = self.embedder.embed_query(query)
        depth = max(top_k, self.pool_depth)
        paragraphs = self.store.search(vector, top_k=depth, filters=filters)
        best: dict[str, dict] = {}
        for paragraph in paragraphs:
            unit_id = (paragraph.get("metadata") or {}).get("unit_id")
            if not unit_id or unit_id not in self.units:
                continue
            current = best.get(unit_id)
            if current is None or paragraph["score"] > current["score"]:
                best[unit_id] = paragraph
        ordered = sorted(best.items(), key=lambda item: (-item[1]["score"], item[0]))
        hits = []
        for rank, (unit_id, paragraph) in enumerate(ordered[:top_k], start=1):
            unit = self.units[unit_id]
            hits.append(
                {
                    "id": unit_id,
                    "text": unit["text"],
                    "source_id": unit["source_id"],
                    "source": unit["source"],
                    "page": unit["page"],
                    "metadata": unit["metadata"],
                    "score": round(float(paragraph["score"]), 6),
                    "rank": rank,
                    "best_paragraph_id": paragraph["id"],
                }
            )
        return hits


def build_day6_retriever(units: list[dict], embedder: Embedder):
    store = DenseStore(DAY6_STORE, collection=DAY6_COLLECTION)
    return DenseDay6BRetriever(store, embedder, units)
