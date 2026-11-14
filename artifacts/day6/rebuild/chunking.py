"""Build traceable retrieval chunks for strategies A, B and C.

A: fixed-size character windows with overlap, reset at every source unit.
B: paragraph-aware chunks, max size, no chunk crosses a unit boundary.
C: exactly the same segmentation as B; only the query filter differs.

Run from starter/:
    python -m src.chunking
"""
from __future__ import annotations

import argparse
import re
from collections import Counter
from typing import Iterable

from .ingestion import DEFAULT_CORPUS, load_corpus_jsonl
from .models import Chunk, DocumentPage

FIXED_SIZE = 500
FIXED_OVERLAP = 50
PARAGRAPH_MAX = 1500
PARAGRAPH_MIN = 300
PARAGRAPH_MAX_OVERSHOOT = 1.2
VALID_STRATEGIES = {"A", "B", "C"}


def _unit_key(page: DocumentPage) -> str:
    return str(page.metadata.get("unit_id") or f"page-{page.page}")


def _make_chunk(
    page: DocumentPage,
    strategy: str,
    index: int,
    start: int,
    end: int,
) -> Chunk | None:
    raw = page.text[start:end]
    left = len(raw) - len(raw.lstrip())
    right = len(raw) - len(raw.rstrip())
    text = raw.strip()
    if not text:
        return None

    unit_id = _unit_key(page)
    metadata = {
        "strategy": strategy,
        "unit_id": unit_id,
        "book": page.metadata.get("book"),
        "section": page.metadata.get("section") or page.metadata.get("book_title"),
        "chunk_index": index,
        "start_char": start + left,
        "end_char": end - right,
    }
    return Chunk(
        chunk_id=f"{strategy}:{unit_id}:{index:04d}",
        document_id=page.document_id,
        source=page.source,
        page=page.page,
        text=text,
        metadata=metadata,
    )


def _fixed_page(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    if size <= 0:
        raise ValueError("size must be positive")
    if overlap < 0 or overlap >= size:
        raise ValueError("overlap must be >= 0 and < size")

    text = page.text
    length = len(text)
    chunks: list[Chunk] = []
    start = 0
    index = 0

    while start < length:
        while start < length and text[start].isspace():
            start += 1
        if start >= length:
            break

        end = min(start + size, length)
        if end < length:
            split = end
            while split > start and not text[split - 1].isspace():
                split -= 1
            if split > start:
                end = split

        chunk = _make_chunk(page, "A", index, start, end)
        if chunk is not None:
            chunks.append(chunk)
            index += 1

        if end >= length:
            break

        next_start = max(start + 1, end - overlap)
        while next_start < end and not text[next_start - 1].isspace():
            next_start += 1
        start = next_start

    return chunks


def _paragraph_ranges(text: str) -> list[tuple[int, int]]:
    """Return trimmed (start, end) ranges for non-empty paragraphs."""
    ranges: list[tuple[int, int]] = []
    for match in re.finditer(r"[^\n]+(?:\n(?!\s*\n)[^\n]+)*", text):
        start, end = match.span()
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if start < end:
            ranges.append((start, end))
    return ranges


def _split_range(text: str, start: int, end: int, max_size: int) -> list[tuple[int, int]]:
    """Split one oversized range at sentence, then word, then hard boundaries."""
    ranges: list[tuple[int, int]] = []
    while end - start > max_size:
        hard_cut = start + max_size
        boundary: int | None = None

        # Prefer sentence boundaries in the second half of the window.
        for pos in range(hard_cut, start + max_size // 2, -1):
            if text[pos - 1] in ".!?" and (pos == end or text[pos].isspace()):
                boundary = pos
                break

        if boundary is None:
            for pos in range(hard_cut, start + max_size // 2, -1):
                if text[pos - 1].isspace():
                    boundary = pos
                    break

        if boundary is None or boundary <= start:
            boundary = hard_cut

        ranges.append((start, boundary))
        start = boundary
        while start < end and text[start].isspace():
            start += 1

    if start < end:
        ranges.append((start, end))
    return ranges


def _paragraph_page(
    page: DocumentPage,
    strategy: str,
    max_size: int,
    min_size: int,
) -> list[Chunk]:
    if max_size <= 0:
        raise ValueError("max_size must be positive")
    if min_size < 0:
        raise ValueError("min_size must be >= 0")

    ranges: list[tuple[int, int]] = []
    buffer_start: int | None = None
    buffer_end: int | None = None

    for start, end in _paragraph_ranges(page.text):
        if end - start > max_size:
            if buffer_start is not None and buffer_end is not None:
                ranges.append((buffer_start, buffer_end))
                buffer_start = buffer_end = None
            ranges.extend(_split_range(page.text, start, end, max_size))
            continue

        if buffer_start is None:
            buffer_start, buffer_end = start, end
        elif end - buffer_start <= max_size:
            buffer_end = end
        else:
            ranges.append((buffer_start, buffer_end))
            buffer_start, buffer_end = start, end

    if buffer_start is not None and buffer_end is not None:
        ranges.append((buffer_start, buffer_end))

    # Merge a tiny trailing chunk into the previous one when it still fits.
    if len(ranges) >= 2:
        last_start, last_end = ranges[-1]
        prev_start, _ = ranges[-2]
        if (last_end - last_start) < min_size and (
            last_end - prev_start
        ) <= max_size * PARAGRAPH_MAX_OVERSHOOT:
            ranges[-2] = (prev_start, last_end)
            ranges.pop()

    chunks: list[Chunk] = []
    for index, (start, end) in enumerate(ranges):
        chunk = _make_chunk(page, strategy, index, start, end)
        if chunk is not None:
            chunks.append(chunk)
    return chunks


def build_chunks(
    pages: Iterable[DocumentPage],
    strategy: str,
    *,
    fixed_size: int = FIXED_SIZE,
    fixed_overlap: int = FIXED_OVERLAP,
    paragraph_max: int = PARAGRAPH_MAX,
    paragraph_min: int = PARAGRAPH_MIN,
) -> list[Chunk]:
    if strategy not in VALID_STRATEGIES:
        raise ValueError(f"strategy must be one of {sorted(VALID_STRATEGIES)}")

    chunks: list[Chunk] = []
    for page in pages:
        if strategy == "A":
            chunks.extend(_fixed_page(page, fixed_size, fixed_overlap))
        else:
            chunks.extend(
                _paragraph_page(page, strategy, paragraph_max, paragraph_min)
            )
    return chunks


def chunk_stats(chunks: Iterable[Chunk]) -> dict[str, object]:
    chunk_list = list(chunks)
    return {
        "chunks": len(chunk_list),
        "by_book": dict(sorted(Counter(c.metadata.get("book") for c in chunk_list).items())),
        "min_chars": min((len(c.text) for c in chunk_list), default=0),
        "max_chars": max((len(c.text) for c in chunk_list), default=0),
        "mean_chars": round(
            sum(len(c.text) for c in chunk_list) / len(chunk_list), 1
        ) if chunk_list else 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and inspect A/B/C chunks")
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    args = parser.parse_args()

    pages = load_corpus_jsonl(args.corpus)
    for strategy in ("A", "B", "C"):
        chunks = build_chunks(pages, strategy)
        stats = chunk_stats(chunks)
        print(f"{strategy}: {stats}")


if __name__ == "__main__":
    main()
