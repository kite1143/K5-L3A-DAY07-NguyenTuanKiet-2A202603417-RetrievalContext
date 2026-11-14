"""Sinh bảng chấm tay cho một run agent: câu hỏi, đáp án chuẩn, câu trả lời, citation.

Với mỗi citation, script in ra câu trong chunk được cite khớp nhiều token nội dung
nhất của đáp án chuẩn, để người chấm đọc và quyết định citation có hỗ trợ hay không.

    python src/review_sheet.py --run artifacts/day7/results/agent-dev-c2 --out artifacts/day7/reviews/dev-c2.md
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "data" / "day6" / "questions.json"
ABSTAIN = ROOT / "data" / "day6" / "abstain.json"
SENTENCE = re.compile(r"(?<=[.!?])\s+")

STOP = set("the a an of to and or in on for that this with as is are was were be by not it its he she they them his her their from at into than which who whom what when where why how all any both each few more most other some only own same too very can will just should now".split())


def content_tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z']+", text.lower()) if token not in STOP and len(token) > 2}


def best_sentence(chunk_text: str, expected: str) -> tuple[int, str]:
    wanted = content_tokens(expected)
    best = (0, "")
    for sentence in SENTENCE.split(chunk_text):
        overlap = len(wanted & content_tokens(sentence))
        if overlap > best[0]:
            best = (overlap, " ".join(sentence.split())[:220])
    return best


def main() -> None:
    parser = argparse.ArgumentParser(description="Bảng chấm tay cho trace agent")
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    traces = json.loads((args.run / "traces.json").read_text(encoding="utf-8"))
    chunks = {
        chunk["id"]: chunk
        for chunk in json.loads((ROOT / "data" / "day6" / "chunks.json").read_text(encoding="utf-8"))
    }
    answerable = {q["id"]: q for q in json.loads(QUESTIONS.read_text(encoding="utf-8"))}
    unanswerable = {a["id"]: a for a in json.loads(ABSTAIN.read_text(encoding="utf-8"))}

    lines = [
        "# Bảng chấm tay — " + args.run.name,
        "",
        "Chấm: 0 = sai/thiếu evidence, 1 = đúng một phần, 2 = đúng và đủ. Từ chối câu có đáp án = 0.",
        "",
    ]
    for trace in traces:
        qid = trace["query_id"]
        question = answerable.get(qid) or unanswerable.get(qid)
        if question is None:
            raise SystemExit(f"không thấy câu {qid}")
        gold_units = {item.get("unit_id") for item in answerable.get(qid, {}).get("gold", [])}
        lines.append("## " + qid + " — status: " + trace["status"])
        lines.append("")
        lines.append("- Câu hỏi: " + question["question"])
        if qid in answerable:
            lines.append("- Đáp án chuẩn: " + answerable[qid]["expected_answer"])
            lines.append("- Gold unit: " + str(sorted(gold_units)))
            lines.append("- Evidence: " + answerable[qid]["gold"][0]["evidence"][:200])
        else:
            lines.append("- Câu thiếu evidence. Lý do: " + question["absence_reason"])
            lines.append("- Hành vi mong đợi: " + question["expected_behavior"])
        lines.append(
            "- Số lượt search: "
            + str(trace["searches"])
            + " | context: "
            + str(trace["context_chars"])
            + " ký tự | context_ids: "
            + str(trace["context_ids"])
        )
        if trace["status"] == "answered":
            lines.append("")
            lines.append("**Trả lời:** " + " ".join(trace["answer"].split()))
            lines.append("")
            for citation in trace["citations"]:
                chunk = chunks.get(citation)
                mark = "GOLD" if citation in gold_units else "ngoài gold"
                if chunk is None:
                    lines.append("- " + citation + " (" + mark + ") — không có trong chunks.json")
                    continue
                overlap, sentence = best_sentence(
                    chunk["text"], answerable.get(qid, {}).get("expected_answer", "")
                )
                lines.append(
                    "- " + citation + " (" + mark + ") — khớp " + str(overlap) + " token nội dung với đáp án chuẩn"
                )
                lines.append("  - câu khớp nhất: " + sentence)
        else:
            lines.append("")
            lines.append("**Từ chối:** " + (trace.get("reason") or ""))
            for event in trace["events"]:
                if event["event"] == "abstain":
                    lines.append("- Model nói: " + str(event.get("reason")))
        lines.append("")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote " + str(args.out) + "  (" + str(len(traces)) + " cases)")


if __name__ == "__main__":
    main()
