"""Hybrid retrieval bằng Reciprocal Rank Fusion (RRF).

RRF chỉ dùng thứ hạng nên không phải chuẩn hoá score giữa dense (cosine) và
BM25 (thang điểm không so sánh được) — đúng yêu cầu BENCHMARK.md: chỉ cộng
score khi có cách chuẩn hoá/hợp nhất hợp lý.
"""
from __future__ import annotations

DEFAULT_RRF_K = 60
DEFAULT_DEPTH = 20


def rrf_fuse(rankings: list[list[dict]], *, k: int = DEFAULT_RRF_K, top_k: int = 3) -> list[dict]:
    if k <= 0:
        raise ValueError("RRF k phải > 0")
    scores: dict[str, float] = {}
    payload: dict[str, dict] = {}
    for ranking in rankings:
        for rank, hit in enumerate(ranking, start=1):
            scores[hit["id"]] = scores.get(hit["id"], 0.0) + 1.0 / (k + rank)
            payload.setdefault(hit["id"], hit)
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    hits = []
    for rank, (chunk_id, score) in enumerate(ordered[:top_k], start=1):
        hit = dict(payload[chunk_id])
        hit["score"] = round(score, 6)
        hit["rank"] = rank
        hit["rrf_score"] = hit["score"]
        hits.append(hit)
    return hits


class HybridRetriever:
    """Kết hợp dense và BM25 trong cùng một lần gọi, cùng filter."""

    def __init__(self, dense, lexical, *, depth: int = DEFAULT_DEPTH, k: int = DEFAULT_RRF_K, method: str = "hybrid") -> None:
        self.dense = dense
        self.lexical = lexical
        self.depth = depth
        self.k = k
        self.method = method

    def search(self, query: str, *, top_k: int = 3, filters: dict | None = None) -> list[dict]:
        dense_hits = self.dense.search(query, top_k=self.depth, filters=filters)
        lexical_hits = self.lexical.search(
            query, top_k=self.depth, filters=filters, candidate_depth=self.depth * 5
        )
        fused = rrf_fuse([dense_hits, lexical_hits], k=self.k, top_k=top_k)
        for hit in fused:
            hit["components"] = {
                "dense_rank": next((h["rank"] for h in dense_hits if h["id"] == hit["id"]), None),
                "bm25_rank": next((h["rank"] for h in lexical_hits if h["id"] == hit["id"]), None),
            }
        return fused
