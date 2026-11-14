"""Chuyển artifact Day 6 (Lab_06) sang hợp đồng dữ liệu Day 7.

Nguồn Day 6 là corpus dạng JSONL: mỗi dòng là một "unit" (nhóm đoạn ~1500 ký tự)
thuộc The Republic, Books I-III, bản dịch Jowett, Project Gutenberg #1497.
Day 7 yêu cầu mảng JSON với khoá: id, text, source_id, source, page, metadata
(xem data/README.md). Script này chỉ đổi tên/chuẩn hoá trường; không suy đoán
evidence, không đọc nhãn test để chỉnh gì.

Chạy từ thư mục gốc repo:

    python src/adapt_day6.py

Sinh ra:
    data/day6/chunks.json     - 111 chunk theo schema Day 7
    data/day6/questions.json  - 20 câu có đáp án (15 dev / 5 test)
    data/day6/manifest.json   - nguồn, phiên bản, sha256, thống kê
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / "data" / "day6" / "raw" / "corpus.jsonl"
DEFAULT_QUESTIONS = ROOT / "data" / "day6" / "raw" / "questions.jsonl"
DEFAULT_OUTPUT = ROOT / "data" / "day6"

EMBEDDING = {
    "provider": "fastembed",
    "model": "BAAI/bge-small-en-v1.5",
    "dimensions": 384,
    "normalized": True,
    "query_prefix": "none (bge-small-en-v1.5 dùng query_embed/passage_embed của fastembed)",
}
STORE = {
    "backend": "chromadb",
    "version": "1.5.9",
    "path": "artifacts/day6/chroma",
    "metric": "cosine",
    "collections": {
        "B": {"name": "republic_B_384", "chunks": 184, "chunking": "paragraph, target 1500/300 chars"},
        "A": {"name": "republic_A_384", "chunks": 498, "chunking": "fixed 500/50 overlap"},
    },
    "note": "Chunk cấp unit dùng cho retrieval bước 3 là collection B; A chỉ là đối chứng chunking của Day 6.",
}


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"không thấy {path}")
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{number} không phải JSON hợp lệ: {exc}") from exc
    return rows


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def convert_chunk(unit: dict) -> dict:
    for key in ("unit_id", "text", "document_id", "source", "page", "book"):
        if key not in unit:
            raise ValueError(f"unit thiếu trường {key}: {unit.get('unit_id')}")
    text = unit["text"]
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"unit {unit['unit_id']} có text rỗng")
    return {
        "id": unit["unit_id"],
        "text": text,
        "source_id": unit["document_id"],
        "source": unit["source"],
        "page": int(unit["page"]),
        "metadata": {
            "unit_id": unit["unit_id"],
            "book": int(unit["book"]),
            "book_title": unit.get("book_title"),
            "section": unit.get("section"),
            "author": unit.get("author"),
            "language": unit.get("language"),
            "start_char": unit.get("start_char"),
            "end_char": unit.get("end_char"),
            "char_count": unit.get("char_count"),
            "trace_unit": "paragraph_group_1500_chars",
            "origin": "day6:plato-republic-books-1-3",
        },
    }


def convert_question(question: dict, unit_by_id: dict[str, dict]) -> dict:
    gold_unit = unit_by_id.get(question["gold_unit_id"])
    if gold_unit is None:
        raise ValueError(f"câu {question['id']} trỏ tới unit không tồn tại: {question['gold_unit_id']}")
    evidence = question["evidence_quote"]
    if evidence not in gold_unit["text"]:
        raise ValueError(f"câu {question['id']}: evidence không phải substring của {question['gold_unit_id']}")
    if int(question["gold_page"]) != int(gold_unit["page"]):
        raise ValueError(f"câu {question['id']}: gold_page lệch với page của unit")
    result = {
        "id": question["id"],
        "split": question["split"],
        "question": question["question"],
        "expected_answer": question["expected_answer"],
        "gold": [
            {
                "source_id": question["gold_source_id"],
                "page": int(question["gold_page"]),
                "evidence": evidence,
                "unit_id": question["gold_unit_id"],
            }
        ],
        "filter": question.get("filter"),
        "type": question.get("type"),
        "gold_unit_id": question["gold_unit_id"],
        "gold_book": int(question["gold_book"]),
        "leakage_risk": question.get("leakage_risk"),
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Chuyển artifact Day 6 sang schema Day 7")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    units = read_jsonl(args.corpus)
    raw_questions = read_jsonl(args.questions)
    if not units:
        raise ValueError("corpus rỗng")
    if not raw_questions:
        raise ValueError("questions rỗng")

    unit_by_id = {unit["unit_id"]: unit for unit in units}
    if len(unit_by_id) != len(units):
        raise ValueError("unit_id không duy nhất trong corpus")

    chunks = [convert_chunk(unit) for unit in units]
    ordered = sorted(chunks, key=lambda chunk: chunk["page"])
    if len({chunk["id"] for chunk in ordered}) != len(ordered):
        raise ValueError("chunk id không duy nhất")
    if [chunk["page"] for chunk in ordered] != list(range(1, len(ordered) + 1)):
        raise ValueError("page phải là 1..N liên tục theo thứ tự unit")

    questions = [convert_question(question, unit_by_id) for question in raw_questions]
    if len({question["id"] for question in questions}) != len(questions):
        raise ValueError("question id không duy nhất")
    if {question["split"] for question in questions} - {"dev", "test"}:
        raise ValueError("split chỉ được là dev hoặc test")

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "chunks.json").write_text(
        json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output / "questions.json").write_text(
        json.dumps(questions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    by_book = Counter(chunk["metadata"]["book"] for chunk in ordered)
    by_split = Counter(question["split"] for question in questions)
    by_type = Counter(question.get("type") for question in questions)
    char_counts = [len(chunk["text"]) for chunk in ordered]

    manifest = {
        "day7_artifact_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generated_by": "src/adapt_day6.py",
        "upstream": {
            "lab": "Day 6 — Retrieval & Vector Store (repo Lab_06)",
            "corpus_id": "plato-republic-books-1-3",
            "corpus_file": "data/day6/raw/corpus.jsonl",
            "corpus_sha256": sha256(args.corpus),
            "questions_file": "data/day6/raw/questions.jsonl",
            "questions_sha256": sha256(args.questions),
        },
        "source_document": {
            "source_id": "plato-republic-1497",
            "title": "The Republic",
            "author": "Plato",
            "translator": "Benjamin Jowett",
            "url": "https://www.gutenberg.org/ebooks/1497",
            "license": "Public domain in the USA; Project Gutenberg License",
            "included_scope": "Books I-III",
        },
        "counts": {
            "chunks": len(ordered),
            "characters": sum(char_counts),
            "min_chars": min(char_counts),
            "max_chars": max(char_counts),
            "chunks_by_book": dict(sorted(by_book.items())),
            "questions": len(questions),
            "questions_by_split": dict(sorted(by_split.items())),
            "questions_by_type": dict(sorted(by_type.items())),
            "questions_with_filter": sum(1 for q in questions if q.get("filter")),
        },
        "page_definition": (
            "page = thứ tự unit trong corpus (1..N). Nguồn là text Gutenberg không có "
            "số trang in, nên Day 7 giữ nguyên quy ước Day 6 và không bịa số trang giấy."
        ),
        "embedding": EMBEDDING,
        "store": STORE,
        "field_mapping": {
            "chunk": {
                "id": "unit_id",
                "source_id": "document_id",
                "page": "page (unit index)",
                "metadata.book": "book",
                "metadata.section": "section",
            },
            "question": {
                "gold[0].source_id": "gold_source_id",
                "gold[0].page": "gold_page",
                "gold[0].evidence": "evidence_quote",
                "gold[0].unit_id": "gold_unit_id (giữ để truy vết)",
            },
        },
        "limits": [
            "Một tài liệu duy nhất, tiếng Anh; không có PDF gốc nên không có số trang in.",
            "Unit dài ~1500 ký tự nên evidence nhiều khả năng nằm trọn trong một chunk; trường hợp bị cắt sẽ ghi riêng khi phân tích lỗi.",
            "Câu thiếu evidence là phần bổ sung của Day 7, nằm ở data/day6/abstain.json.",
        ],
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"chunks={len(ordered)} characters={sum(char_counts)} by_book={dict(sorted(by_book.items()))}")
    print(f"questions={len(questions)} by_split={dict(sorted(by_split.items()))} by_type={dict(sorted(by_type.items()))}")
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
