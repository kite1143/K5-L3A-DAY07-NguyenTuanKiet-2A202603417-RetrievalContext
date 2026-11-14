"""Tool retrieval cho agent.

Filter chỉ đến từ câu hỏi (người dùng cung cấp trước khi truy xuất). Model chọn
tool và query, không chọn filter, nên không thể suy ra gold từ filter.
"""
from __future__ import annotations

TOOL_TO_METHOD = {
    "dense_search": "dense",
    "lexical_search": "bm25",
    "hybrid_search": "hybrid",
}


class ToolError(RuntimeError):
    pass


class RetrievalTools:
    def __init__(self, retrievers: dict, *, top_k: int = 5, max_top_k: int = 10) -> None:
        self.retrievers = retrievers
        self.top_k = top_k
        self.max_top_k = max_top_k

    @property
    def names(self) -> list[str]:
        return [name for name in TOOL_TO_METHOD if TOOL_TO_METHOD[name] in self.retrievers]

    def run(self, name: str, query: str, *, filters: dict | None, top_k: int | None = None) -> list[dict]:
        method = TOOL_TO_METHOD.get(name)
        if method is None:
            raise ToolError(f"tool không hỗ trợ: {name!r}")
        retriever = self.retrievers.get(method)
        if retriever is None:
            raise ToolError(f"retriever chưa cấu hình: {method}")
        if not isinstance(query, str) or not query.strip():
            raise ToolError("query phải là chuỗi không rỗng")
        requested = self.top_k if top_k is None else int(top_k)
        if not 1 <= requested <= self.max_top_k:
            raise ToolError(f"top_k phải trong 1..{self.max_top_k}")
        hits = retriever.search(query, top_k=requested, filters=filters)
        for hit in hits:
            hit["tool"] = name
        return hits
