"""Đánh giá retrieval theo định nghĩa của BENCHMARK.md.

- Hit@1: chunk top-1 đúng source_id + page và chứa nguyên văn evidence.
- Evidence Hit@3: một trong top-3 thoả cùng điều kiện.
- Context Evidence Rate: evidence có trong context cuối gửi model / số câu.
- Câu thiếu evidence không nằm trong mẫu số (nguồn là data/day6/questions.json).
"""
from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

from .context import DEFAULT_BUDGET, pack_context

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS_PATH = ROOT / "data" / "day6" / "questions.json"


def is_hit(hit: dict, gold: list[dict]) -> bool:
    for item in gold:
        if (
            hit.get("source_id") == item.get("source_id")
            and int(hit.get("page")) == int(item.get("page"))
            and item.get("evidence", "") in hit.get("text", "")
        ):
            return True
    return False


def load_questions(split: str | None = None, path: Path = QUESTIONS_PATH) -> list[dict]:
    questions = json.loads(path.read_text(encoding="utf-8"))
    if split:
        questions = [q for q in questions if q.get("split") == split]
    if not questions:
        raise ValueError("không có câu hỏi cho split này")
    return questions


def evaluate(
    retriever,
    questions: list[dict],
    *,
    top_k: int = 3,
    context_budget: int = DEFAULT_BUDGET,
    context_depth: int = 5,
) -> dict:
    depth = max(top_k, context_depth)
    traces = []
    for question in questions:
        filters = question.get("filter")
        started = time.perf_counter()
        hits = retriever.search(question["question"], top_k=depth, filters=filters)
        elapsed_ms = (time.perf_counter() - started) * 1000
        if len(hits) > depth:
            raise ValueError(f"{question['id']}: retriever trả quá {depth} kết quả")
        if len({hit['id'] for hit in hits}) != len(hits):
            raise ValueError(f"{question['id']}: retriever trả ID trùng")

        ranked = hits[:top_k]
        context, context_ids = pack_context(hits, budget=context_budget)
        gold = question["gold"]
        hit_flags = [is_hit(hit, gold) for hit in ranked]
        traces.append(
            {
                "query_id": question["id"],
                "split": question["split"],
                "type": question.get("type"),
                "question": question["question"],
                "filter": filters,
                "gold": gold,
                "top_k": top_k,
                "results": [
                    {
                        "rank": rank,
                        "id": hit["id"],
                        "page": hit.get("page"),
                        "score": hit.get("score"),
                        "hit": flag,
                    }
                    for rank, (hit, flag) in enumerate(zip(ranked, hit_flags), start=1)
                ],
                "hit1": bool(hit_flags and hit_flags[0]),
                "hit3": any(hit_flags),
                "context": context,
                "context_ids": context_ids,
                "context_chars": len(context),
                "context_budget": context_budget,
                "context_hit": any(
                    is_hit(hit, gold) and hit["id"] in context_ids for hit in hits
                ),
                "elapsed_ms": elapsed_ms,
            }
        )

    n = len(traces)
    summary = {
        "method": getattr(retriever, "method", type(retriever).__name__),
        "n": n,
        "hit1": sum(t["hit1"] for t in traces),
        "hit3": sum(t["hit3"] for t in traces),
        "hit1_rate": round(sum(t["hit1"] for t in traces) / n, 4),
        "hit3_rate": round(sum(t["hit3"] for t in traces) / n, 4),
        "context_hit": sum(t["context_hit"] for t in traces),
        "context_hit_rate": round(sum(t["context_hit"] for t in traces) / n, 4),
        "avg_context_chars": round(statistics.mean(t["context_chars"] for t in traces), 1),
        "median_ms": round(statistics.median(t["elapsed_ms"] for t in traces), 3),
        "context_budget": context_budget,
        "top_k": top_k,
    }
    subset = [t for t in traces if t["filter"]]
    if subset:
        summary["filter_subset"] = {
            "n": len(subset),
            "hit1": sum(t["hit1"] for t in subset),
            "hit3": sum(t["hit3"] for t in subset),
        }
    return {"summary": summary, "traces": traces}


def write_result(result: dict, output: Path, *, run_config: dict | None = None) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "traces.json").write_text(
        json.dumps(result["traces"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output / "summary.json").write_text(
        json.dumps(result["summary"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if run_config is not None:
        (output / "run_config.json").write_text(
            json.dumps(run_config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
