"""Chạy và so sánh các phương pháp retrieval trên dev (hoặc test sau khi chốt).

    python src/run_retrieval.py --methods dense,bm25,hybrid --split dev
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from retrieval.context import DEFAULT_BUDGET
from retrieval.dense import DIMENSIONS, MODEL_NAME
from retrieval.evaluate import evaluate, load_questions, write_result
from retrieval.registry import METHODS, build_retriever

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Chạy retrieval và ghi metric theo BENCHMARK.md")
    parser.add_argument("--methods", default="dense,bm25,hybrid")
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--context-depth", type=int, default=5)
    parser.add_argument("--context-budget", type=int, default=DEFAULT_BUDGET)
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts" / "day7" / "results")
    args = parser.parse_args()

    selected = [name.strip() for name in args.methods.split(",") if name.strip()]
    unknown = set(selected) - set(METHODS)
    if unknown:
        raise SystemExit(f"phương pháp không hỗ trợ: {sorted(unknown)}")

    questions = load_questions(args.split)
    rows = []
    for method in selected:
        retriever = build_retriever(method)
        result = evaluate(
            retriever,
            questions,
            top_k=args.top_k,
            context_budget=args.context_budget,
            context_depth=args.context_depth,
        )
        output = args.out / f"{args.split}-{method}"
        config = {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "method": method,
            "split": args.split,
            "top_k": args.top_k,
            "context_depth": args.context_depth,
            "context_budget": args.context_budget,
            "questions": len(questions),
            "embedding": {"provider": "fastembed", "model": MODEL_NAME, "dimensions": DIMENSIONS},
            "hybrid": {"fusion": "rrf", "k": 60, "depth": 20} if method == "hybrid" else None,
            "bm25": {"k1": 1.5, "b": 0.75} if method in ("bm25", "hybrid") else None,
        }
        write_result(result, output, run_config=config)
        rows.append(result["summary"])
        print(json.dumps(result["summary"], ensure_ascii=False))

    table = {row["method"]: row for row in rows}
    (args.out / f"{args.split}-retrieval-comparison.json").write_text(
        json.dumps(table, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("\nmethod    Hit@1      Evidence Hit@3  Context Ev. Rate  avg_ctx  median_ms")
    for row in rows:
        print(
            f"{row['method']:<9} {row['hit1']:>2}/{row['n']:<2} {row['hit1_rate']:>6.1%}  "
            f"{row['hit3']:>2}/{row['n']:<2} {row['hit3_rate']:>6.1%}  "
            f"{row['context_hit']:>2}/{row['n']:<2} {row['context_hit_rate']:>6.1%}      "
            f"{row['avg_context_chars']:>6.0f}  {row['median_ms']:>8.2f}"
        )


if __name__ == "__main__":
    main()
