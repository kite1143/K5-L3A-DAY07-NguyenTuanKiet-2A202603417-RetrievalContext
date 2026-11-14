"""Read and normalize the Day 06 corpus.

The corpus is stored as JSONL: one source unit per line. Each unit already has
traceability metadata (unit_id, page, book, section) produced by
tools/build_corpus.py.

Run from starter/:
    python -m src.ingestion
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from .models import DocumentPage

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS = ROOT / "data" / "corpus.jsonl"
REQUIRED_FIELDS = (
    "document_id",
    "source",
    "page",
    "unit_id",
    "book",
    "text",
)
VALID_BOOKS = {1, 2, 3}


class CorpusValidationError(ValueError):
    """Raised when a corpus row cannot be traced back to a source unit."""


def normalize_text(text: str) -> str:
    """Normalize Unicode and whitespace while preserving paragraph breaks."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ")
    text = unicodedata.normalize("NFC", text)

    paragraphs: list[str] = []
    for block in re.split(r"\n\s*\n", text):
        block = re.sub(r"[ \t\f\v]+", " ", block)
        block = re.sub(r" *\n *", "\n", block)
        block = block.strip()
        if block:
            paragraphs.append(block)
    return "\n\n".join(paragraphs)


def _require(row: dict[str, Any], field: str, line_no: int) -> Any:
    if field not in row or row[field] is None:
        raise CorpusValidationError(f"line {line_no}: missing field {field!r}")
    return row[field]


def load_corpus_jsonl(
    path: str | Path = DEFAULT_CORPUS,
    *,
    normalize: bool = False,
) -> list[DocumentPage]:
    """Load and validate one JSONL corpus file.

    'normalize=False' is the default because the committed corpus is already
    normalized and benchmark evidence quotes were verified against its exact
    text. Set 'normalize=True' only for newly ingested, unnormalized text.
    """
    corpus_path = Path(path)
    if not corpus_path.is_file():
        raise FileNotFoundError(f"corpus file not found: {corpus_path}")

    pages: list[DocumentPage] = []
    seen_units: set[str] = set()
    expected_page = 1

    with corpus_path.open(encoding="utf-8") as handle:
        for line_no, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CorpusValidationError(
                    f"line {line_no}: invalid JSON: {exc.msg}"
                ) from exc
            if not isinstance(row, dict):
                raise CorpusValidationError(f"line {line_no}: expected a JSON object")

            for field in REQUIRED_FIELDS:
                _require(row, field, line_no)

            unit_id = str(row["unit_id"]).strip()
            document_id = str(row["document_id"]).strip()
            source = str(row["source"]).strip()
            page = row["page"]
            book = row["book"]
            text = row["text"]

            if not unit_id:
                raise CorpusValidationError(f"line {line_no}: empty unit_id")
            if unit_id in seen_units:
                raise CorpusValidationError(
                    f"line {line_no}: duplicate unit_id {unit_id!r}"
                )
            if not document_id:
                raise CorpusValidationError(f"line {line_no}: empty document_id")
            if not source:
                raise CorpusValidationError(f"line {line_no}: empty source")
            if not isinstance(page, int) or isinstance(page, bool):
                raise CorpusValidationError(f"line {line_no}: page must be an integer")
            if page != expected_page:
                raise CorpusValidationError(
                    f"line {line_no}: page {page} breaks the 1..N sequence; "
                    f"expected {expected_page}"
                )
            if not isinstance(book, int) or isinstance(book, bool):
                raise CorpusValidationError(f"line {line_no}: book must be an integer")
            if book not in VALID_BOOKS:
                raise CorpusValidationError(
                    f"line {line_no}: book must be one of {sorted(VALID_BOOKS)}"
                )
            if not isinstance(text, str) or not text.strip():
                raise CorpusValidationError(f"line {line_no}: empty text")

            if "char_count" in row:
                recorded = row["char_count"]
                if not isinstance(recorded, int) or isinstance(recorded, bool):
                    raise CorpusValidationError(
                        f"line {line_no}: char_count must be an integer"
                    )
                if recorded != len(text):
                    raise CorpusValidationError(
                        f"line {line_no}: char_count {recorded} != text length {len(text)}"
                    )

            normalized_text = normalize_text(text) if normalize else text
            metadata = {
                "unit_id": unit_id,
                "book": book,
                "book_title": row.get("book_title", f"BOOK {book}"),
                "section": row.get("section", row.get("book_title", f"BOOK {book}")),
                "author": row.get("author"),
                "language": row.get("language"),
                "char_count": len(text),
                "start_char": row.get("start_char"),
                "end_char": row.get("end_char"),
            }
            pages.append(
                DocumentPage(
                    document_id=document_id,
                    source=source,
                    page=page,
                    text=normalized_text,
                    metadata=metadata,
                )
            )
            seen_units.add(unit_id)
            expected_page += 1

    if not pages:
        raise CorpusValidationError(f"corpus is empty: {corpus_path}")
    return pages


def corpus_stats(pages: Iterable[DocumentPage]) -> dict[str, Any]:
    """Return counts used by the pipeline and the report."""
    page_list = list(pages)
    books = Counter(page.metadata.get("book") for page in page_list)
    return {
        "documents": len({page.document_id for page in page_list}),
        "pages": len(page_list),
        "books": dict(sorted(books.items())),
        "char_count": sum(len(page.text) for page in page_list),
        "word_count_approx": sum(len(page.text.split()) for page in page_list),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect the Day 06 corpus")
    parser.add_argument(
        "--corpus",
        type=Path,
        default=DEFAULT_CORPUS,
        help=f"Path to corpus JSONL (default: {DEFAULT_CORPUS})",
    )
    args = parser.parse_args()

    pages = load_corpus_jsonl(args.corpus)
    stats = corpus_stats(pages)
    print(f"corpus={args.corpus}")
    print(f"documents={stats['documents']}")
    print(f"pages={stats['pages']}")
    print(f"books={stats['books']}")
    print(f"char_count={stats['char_count']}")
    print(f"word_count_approx={stats['word_count_approx']}")
    print(f"first_unit={pages[0].metadata['unit_id']} page={pages[0].page}")
    print(f"last_unit={pages[-1].metadata['unit_id']} page={pages[-1].page}")


if __name__ == "__main__":
    main()
