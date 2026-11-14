"""Chọn context gửi model: dedup, giữ thứ tự liên quan, tôn trọng budget ký tự.

Budget mặc định 4000 ký tự vì unit Day 6 dài 1.500-4.800 ký tự; budget 800 của
starter luôn cho context rỗng với corpus này.
"""
from __future__ import annotations

DEFAULT_BUDGET = 4000


def format_block(hit: dict) -> str:
    page = hit.get("page")
    return f"[{hit['id']} | {hit.get('source_id')} | page {page}]\n{hit['text']}"


def pack_context(hits: list[dict], *, budget: int = DEFAULT_BUDGET) -> tuple[str, list[str]]:
    """Chọn block theo thứ hạng cho tới khi vượt budget; bỏ block không vừa."""
    if budget <= 0:
        raise ValueError("budget phải > 0")
    blocks: list[str] = []
    ids: list[str] = []
    seen: set[str] = set()
    used = 0
    for hit in hits:
        if hit["id"] in seen:
            continue
        block = format_block(hit)
        extra = len(block) + (2 if blocks else 0)
        if used + extra > budget:
            continue
        blocks.append(block)
        ids.append(hit["id"])
        seen.add(hit["id"])
        used += extra
    return "\n\n".join(blocks), ids
