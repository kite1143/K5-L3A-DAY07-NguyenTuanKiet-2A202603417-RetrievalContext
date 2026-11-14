"""Chọn context gửi model: dedup, giữ thứ tự liên quan, tôn trọng budget ký tự.

Hai chế độ:

- `block_cap=None` (mặc định): chỉ nhận block vừa budget — đơn vị văn bản nguyên vẹn.
- `block_cap=N`: nếu block dài hơn N, trích cửa sổ câu quanh câu khớp query nhiều nhất,
  nhờ đó context chứa được nhiều unit hơn trong cùng budget (xem docs/STEP5_RESULTS.md).

Budget 4.000 mặc định vì unit Day 6 dài 1.502-4.762 ký tự; budget 800 của starter
luôn cho context rỗng với corpus này.
"""
from __future__ import annotations

import re

from .text import tokenize

DEFAULT_BUDGET = 4000
DEFAULT_BLOCK_CAP = 1400
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def format_block(hit: dict) -> str:
    page = hit.get("page")
    return f"[{hit['id']} | {hit.get('source_id')} | page {page}]\n{hit['text']}"


def excerpt(text: str, query_terms: set[str], cap: int) -> str:
    """Cắt cửa sổ câu quanh câu khớp query nhiều nhất, giữ độ dài <= cap."""
    if len(text) <= cap:
        return text
    sentences = [sentence.strip() for sentence in SENTENCE_SPLIT.split(text) if sentence.strip()]
    if not sentences:
        return text[:cap]
    scores = [len(set(tokenize(sentence)) & query_terms) for sentence in sentences]
    best = max(range(len(sentences)), key=lambda index: (scores[index], -index))
    start = end = best
    total = len(sentences[best])
    while True:
        grew = False
        if start > 0:
            left = total + len(sentences[start - 1]) + 1
            if left <= cap:
                start -= 1
                total = left
                grew = True
        if end < len(sentences) - 1:
            right = total + len(sentences[end + 1]) + 1
            if right <= cap:
                end += 1
                total = right
                grew = True
        if not grew:
            break
    body = " ".join(sentences[start:end + 1])
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(sentences) - 1 else ""
    return f"{prefix}{body}{suffix}"[:cap]


def pack_context(
    hits: list[dict],
    *,
    budget: int = DEFAULT_BUDGET,
    query: str | None = None,
    block_cap: int | None = None,
) -> tuple[str, list[str]]:
    """Chọn block theo thứ hạng cho tới khi vượt budget; bỏ block không vừa."""
    if budget <= 0:
        raise ValueError("budget phải > 0")
    if block_cap is not None and block_cap <= 0:
        raise ValueError("block_cap phải > 0")
    query_terms = set(tokenize(query)) if query else set()
    blocks: list[str] = []
    ids: list[str] = []
    seen: set[str] = set()
    used = 0
    for hit in hits:
        if hit["id"] in seen:
            continue
        text = hit["text"]
        if block_cap is not None and len(text) > block_cap:
            text = excerpt(text, query_terms, block_cap)
        header = f"[{hit['id']} | {hit.get('source_id')} | page {hit.get('page')}]\n"
        block = header + text
        extra = len(block) + (2 if blocks else 0)
        if used + extra > budget:
            continue
        blocks.append(block)
        ids.append(hit["id"])
        seen.add(hit["id"])
        used += extra
    return "\n\n".join(blocks), ids
