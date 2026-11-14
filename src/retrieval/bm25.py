"""BM25Okapi thuần Python, không phụ thuộc thư viện ngoài.

Dùng cùng bộ chunk với dense (111 unit) để so sánh công bằng: cùng đơn vị văn
bản, cùng câu hỏi, cùng bộ nhãn.
"""
from __future__ import annotations

import math
from collections import Counter

from .text import tokenize


class BM25Index:
    method = "bm25"

    def __init__(self, chunks: list[dict], *, k1: float = 1.5, b: float = 0.75) -> None:
        if not chunks:
            raise ValueError("chunks rỗng")
        if k1 <= 0 or not 0 <= b <= 1:
            raise ValueError("k1 phải > 0 và b trong [0, 1]")
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self.tokens = [tokenize(chunk["text"]) for chunk in chunks]
        self.lengths = [len(row) for row in self.tokens]
        self.avg_length = sum(self.lengths) / len(self.lengths) or 1.0
        document_frequency: Counter[str] = Counter()
        for row in self.tokens:
            document_frequency.update(set(row))
        total = len(chunks)
        self.idf = {
            term: math.log(1 + (total - count + 0.5) / (count + 0.5))
            for term, count in document_frequency.items()
        }

    def _score(self, query_terms: list[str], index: int) -> float:
        counts = Counter(self.tokens[index])
        length_norm = 1 - self.b + self.b * (self.lengths[index] / self.avg_length)
        score = 0.0
        for term in query_terms:
            frequency = counts.get(term)
            if not frequency:
                continue
            score += self.idf.get(term, 0.0) * (
                frequency * (self.k1 + 1) / (frequency + self.k1 * length_norm)
            )
        return score

    def search(
        self,
        query: str,
        *,
        top_k: int = 3,
        filters: dict | None = None,
        candidate_depth: int | None = None,
    ) -> list[dict]:
        if top_k <= 0:
            raise ValueError("top_k phải > 0")
        query_terms = tokenize(query)
        if not query_terms:
            return []
        book = (filters or {}).get("book")
        scored: list[tuple[float, int]] = []
        for index, chunk in enumerate(self.chunks):
            if book is not None and chunk["metadata"].get("book") != book:
                continue
            score = self._score(query_terms, index)
            if score > 0:
                scored.append((score, index))
        scored.sort(key=lambda item: (-item[0], self.chunks[item[1]]["id"]))
        depth = candidate_depth or top_k
        hits = []
        for rank, (score, index) in enumerate(scored[:depth], start=1):
            chunk = self.chunks[index]
            hits.append(
                {
                    "id": chunk["id"],
                    "text": chunk["text"],
                    "source_id": chunk["source_id"],
                    "source": chunk["source"],
                    "page": chunk["page"],
                    "metadata": chunk["metadata"],
                    "score": round(float(score), 6),
                    "rank": rank,
                }
            )
        return hits[:top_k]
