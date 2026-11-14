"""Kiểm tra benchmark Day 7 và (tùy chọn) đóng băng hash.

Kiểm tra theo BENCHMARK.md và SUBMISSION.md:

  * tối thiểu 20 câu có đáp án, dev >= 15, test >= 5;
  * tối thiểu 4 câu thiếu evidence, dev >= 2, test >= 2;
  * mỗi evidence là substring của đúng chunk (source_id + page khớp);
  * filter chỉ dùng metadata 'book', không chứa unit/page gold;
  * câu thiếu evidence không nằm trong mẫu số retrieval;
  * sau khi đóng băng: hash chunks.json / questions.json / abstain.json không đổi.

Chạy từ thư mục gốc repo:

    python src/validate_benchmark.py            # kiểm tra
    python src/validate_benchmark.py --freeze   # ghi/ghi đè hash đóng băng
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "day6"
CHUNKS = DATA / "chunks.json"
QUESTIONS = DATA / "questions.json"
ABSTAIN = DATA / "abstain.json"
MANIFEST = DATA / "manifest.json"
FREEZE = DATA / "benchmark_manifest.json"

ALLOWED_FILTERS = {"book"}
FORBIDDEN_FILTER_KEYS = {"unit_id", "page", "gold_unit_id", "gold_page", "chunk", "chunk_id", "evidence"}
MIN_CHUNKS = 30
MIN_ANSWERABLE = {"total": 20, "dev": 15, "test": 5}
MIN_ABSTAIN = {"total": 4, "dev": 2, "test": 2}

errors: list[str] = []
warnings: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def warn(message: str) -> None:
    warnings.append(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load(path: Path) -> Any:
    if not path.exists():
        fail(f"thiếu file {path.relative_to(ROOT)}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"{path.relative_to(ROOT)} không phải JSON hợp lệ: {exc}")
        return None


def check_chunks(chunks: list[dict]) -> dict[str, dict]:
    if not chunks:
        fail("chunks.json rỗng")
        return {}
    if len(chunks) < MIN_CHUNKS:
        fail(f"chỉ có {len(chunks)} chunk, cần >= {MIN_CHUNKS} đơn vị nội dung")
    by_id: dict[str, dict] = {}
    for chunk in chunks:
        missing = [k for k in ("id", "text", "source_id", "source", "page", "metadata") if k not in chunk]
        if missing:
            fail(f"chunk thiếu trường {missing}: {chunk.get('id')}")
            continue
        chunk_id = chunk["id"]
        if chunk_id in by_id:
            fail(f"chunk id trùng: {chunk_id}")
        by_id[chunk_id] = chunk
        if not isinstance(chunk["text"], str) or not chunk["text"].strip():
            fail(f"chunk {chunk_id} có text rỗng")
        if not isinstance(chunk["metadata"], dict):
            fail(f"chunk {chunk_id} thiếu metadata object")
            continue
        if chunk["metadata"].get("book") not in (1, 2, 3):
            fail(f"chunk {chunk_id} có book ngoài 1..3")
    pages = sorted(int(chunk["page"]) for chunk in by_id.values())
    if pages and pages[0] != 1:
        warn(f"page bắt đầu từ {pages[0]} thay vì 1")
    if pages and len(set(pages)) != len(pages):
        fail("có nhiều chunk cùng page; quy ước Day 7 cần page phân biệt")
    return by_id


def resolve_gold(chunks: list[dict], gold: dict) -> list[dict]:
    return [
        chunk
        for chunk in chunks
        if chunk["source_id"] == gold["source_id"]
        and int(chunk["page"]) == int(gold["page"])
        and gold["evidence"] in chunk["text"]
    ]


def check_questions(questions: list[dict], chunks: list[dict]) -> None:
    if not questions:
        fail("questions.json rỗng")
        return
    ids: set[str] = set()
    evidence_seen: dict[str, str] = {}
    by_split = Counter()
    for question in questions:
        qid = question.get("id")
        if not isinstance(qid, str) or not qid.strip():
            fail(f"câu thiếu id hợp lệ: {question}")
            continue
        if qid in ids:
            fail(f"question id trùng: {qid}")
        ids.add(qid)
        split = question.get("split")
        if split not in ("dev", "test"):
            fail(f"{qid}: split phải là dev/test, đang là {split!r}")
            continue
        by_split[split] += 1
        text = question.get("question")
        if not isinstance(text, str) or not text.strip():
            fail(f"{qid}: thiếu question")
        answer = question.get("expected_answer")
        if not isinstance(answer, str) or not answer.strip():
            fail(f"{qid}: thiếu expected_answer")
        elif text and answer.strip().casefold() in text.casefold():
            warn(f"{qid}: expected_answer xuất hiện nguyên văn trong câu hỏi (rò rỉ đáp án)")
        gold = question.get("gold")
        if not isinstance(gold, list) or not gold:
            fail(f"{qid}: gold phải là danh sách không rỗng")
            continue
        for index, item in enumerate(gold):
            if not isinstance(item, dict):
                fail(f"{qid}: gold[{index}] phải là object")
                continue
            missing = [k for k in ("source_id", "page", "evidence") if item.get(k) in (None, "")]
            if missing:
                fail(f"{qid}: gold[{index}] thiếu {missing}")
                continue
            matches = resolve_gold(chunks, item)
            if not matches:
                fail(f"{qid}: evidence không nằm trọn trong chunk đúng source_id/page")
                continue
            evidence = item["evidence"]
            if evidence in evidence_seen:
                fail(f"{qid}: evidence trùng với {evidence_seen[evidence]}")
            evidence_seen[evidence] = qid
            unit_id = item.get("unit_id")
            if unit_id and unit_id not in {chunk["id"] for chunk in matches}:
                warn(f"{qid}: unit_id {unit_id} không khớp chunk tìm được")
        filter_value = question.get("filter")
        if filter_value is not None:
            if not isinstance(filter_value, dict):
                fail(f"{qid}: filter phải là object hoặc null")
            else:
                unknown = set(filter_value) - ALLOWED_FILTERS
                if unknown:
                    fail(f"{qid}: filter có khoá ngoài {sorted(ALLOWED_FILTERS)}: {sorted(unknown)}")
                leaked = set(filter_value) & FORBIDDEN_FILTER_KEYS
                if leaked:
                    fail(f"{qid}: filter chứa thông tin gold: {sorted(leaked)}")
                book = filter_value.get("book")
                if book is not None and book not in (1, 2, 3):
                    fail(f"{qid}: filter.book phải là 1..3, đang là {book!r}")
                gold_book = question.get("gold_book")
                if book is not None and gold_book is not None and int(book) != int(gold_book):
                    fail(f"{qid}: filter.book={book} mâu thuẫn gold_book={gold_book}")

    for split, minimum in (("dev", MIN_ANSWERABLE["dev"]), ("test", MIN_ANSWERABLE["test"])):
        if by_split[split] < minimum:
            fail(f"câu có đáp án: {split}={by_split[split]} < {minimum}")
    if sum(by_split.values()) < MIN_ANSWERABLE["total"]:
        fail(f"câu có đáp án: tổng {sum(by_split.values())} < {MIN_ANSWERABLE['total']}")


def check_abstain(abstain: list[dict], answerable_ids: set[str], chunks: list[dict]) -> None:
    if not abstain:
        fail("abstain.json rỗng")
        return
    ids: set[str] = set()
    by_split = Counter()
    chunk_ids = {chunk["id"] for chunk in chunks}
    for item in abstain:
        qid = item.get("id")
        if not isinstance(qid, str) or not qid.strip():
            fail(f"câu thiếu evidence có id không hợp lệ: {item}")
            continue
        if qid in ids:
            fail(f"abstain id trùng: {qid}")
        if qid in answerable_ids:
            fail(f"{qid}: id vừa có đáp án vừa thiếu evidence")
        ids.add(qid)
        split = item.get("split")
        if split not in ("dev", "test"):
            fail(f"{qid}: split phải là dev/test")
            continue
        by_split[split] += 1
        if item.get("answerable") is not False:
            fail(f"{qid}: phải có answerable=false")
        if item.get("expected_behavior") != "search_and_abstain":
            fail(f"{qid}: expected_behavior phải là search_and_abstain")
        reason = item.get("absence_reason")
        if not isinstance(reason, str) or len(reason.strip()) < 20:
            fail(f"{qid}: absence_reason phải mô tả cách kiểm tra (>= 20 ký tự)")
        if not isinstance(item.get("question"), str) or not item["question"].strip():
            fail(f"{qid}: thiếu question")
        for unit_id in item.get("near_topic_units", []):
            if unit_id not in chunk_ids:
                fail(f"{qid}: near_topic_units có unit không tồn tại: {unit_id}")
        review = item.get("review")
        if not isinstance(review, dict) or review.get("decision") != "confirmed_absent":
            fail(f"{qid}: thiếu review.decision='confirmed_absent' sau khi đọc hit")

    for split, minimum in (("dev", MIN_ABSTAIN["dev"]), ("test", MIN_ABSTAIN["test"])):
        if by_split[split] < minimum:
            fail(f"câu thiếu evidence: {split}={by_split[split]} < {minimum}")
    if sum(by_split.values()) < MIN_ABSTAIN["total"]:
        fail(f"câu thiếu evidence: tổng {sum(by_split.values())} < {MIN_ABSTAIN['total']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Kiểm tra và đóng băng benchmark Day 7")
    parser.add_argument("--freeze", action="store_true", help="ghi hash đóng băng vào benchmark_manifest.json")
    args = parser.parse_args()

    chunks = load(CHUNKS)
    questions = load(QUESTIONS)
    abstain = load(ABSTAIN)
    manifest = load(MANIFEST)

    if errors:
        report()
        return 1

    by_id = check_chunks(chunks)
    check_questions(questions, chunks)
    answerable_ids = {q.get("id") for q in questions}
    check_abstain(abstain, answerable_ids, chunks)

    if manifest:
        counts = manifest.get("counts", {})
        if counts.get("chunks") not in (None, len(chunks)):
            fail(f"manifest.json ghi {counts.get('chunks')} chunk nhưng thực tế {len(chunks)}")
        if counts.get("questions") not in (None, len(questions)):
            fail(f"manifest.json ghi {counts.get('questions')} câu nhưng thực tế {len(questions)}")

    hashes = {
        "chunks.json": sha256(CHUNKS),
        "questions.json": sha256(QUESTIONS),
        "abstain.json": sha256(ABSTAIN),
    }

    if args.freeze:
        by_split = Counter(q["split"] for q in questions)
        abstain_split = Counter(a["split"] for a in abstain)
        payload = {
            "benchmark_version": "day7-v1",
            "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": "frozen",
            "files": {name: {"sha256": digest} for name, digest in hashes.items()},
            "counts": {
                "answerable": len(questions),
                "answerable_dev": by_split["dev"],
                "answerable_test": by_split["test"],
                "abstain": len(abstain),
                "abstain_dev": abstain_split["dev"],
                "abstain_test": abstain_split["test"],
                "total": len(questions) + len(abstain),
            },
            "policy": {
                "test_creation": "Test kế thừa từ Day 6 (5 câu) cộng 2 câu thiếu evidence; tạo xong mới chạy pipeline.",
                "no_tuning_on_test": "Test chỉ chạy sau khi chốt cấu hình trên dev; nếu buộc phải chỉnh, tạo benchmark v2 và báo riêng.",
                "abstain_excluded_from_retrieval": "Câu thiếu evidence không vào mẫu số Hit@1 / Evidence Hit@3.",
                "filter_policy": "Chỉ dùng metadata book, cấp trước khi truy xuất, không chứa unit/page gold.",
            },
            "derivation": {
                "day6_source": "data/day6/raw/questions.jsonl (20 câu, 15 dev / 5 test)",
                "added_by_day7": "data/day6/abstain.json (4 câu thiếu evidence: 2 dev, 2 test)",
                "verified_by": [
                    "src/validate_benchmark.py",
                    "src/check_absence.py -> data/day6/abstain_checks.json",
                ],
            },
        }
        FREEZE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    elif FREEZE.exists():
        frozen = json.loads(FREEZE.read_text(encoding="utf-8"))
        for name, digest in hashes.items():
            expected = frozen.get("files", {}).get(name, {}).get("sha256")
            if expected and expected != digest:
                fail(f"{name} đã đổi sau khi đóng băng: {expected[:12]}… -> {digest[:12]}…")
    else:
        warn("chưa có benchmark_manifest.json; chạy với --freeze sau khi chốt bộ câu hỏi")

    report()
    return 1 if errors else 0


def report() -> None:
    print(f"errors={len(errors)} warnings={len(warnings)}")
    for message in errors:
        print(f"  ERROR   {message}")
    for message in warnings:
        print(f"  WARN    {message}")
    if not errors:
        print("OK: benchmark hợp lệ theo BENCHMARK.md (20+ câu có evidence, 4 câu thiếu evidence).")


if __name__ == "__main__":
    sys.exit(main())
