"""Chạy agent thật trên dev/test và ghi trace.

    python src/run_agent.py --split dev --out artifacts/day7/results/agent-dev-hybrid

Cần model thật (xem src/agent/providers.py):

    $env:DAY7_LLM_PROVIDER="openai"
    $env:DAY7_LLM_MODEL="gpt-4o-mini"
    $env:DAY7_LLM_BASE_URL="https://api.openai.com/v1"
    $env:DAY7_LLM_API_KEY="..."

Cờ `--scripted-demo` chỉ chạy kịch bản để kiểm tra đường ống; kết quả được đánh
dấu `benchmark_result = false` và không được dùng trong báo cáo.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from agent.controller import LLMController
from agent.loop import run_agent
from config import load_env
from agent.providers import ProviderError, model_from_env
from agent.scripted import ScriptedController
from agent.tools import RetrievalTools
from retrieval.registry import METHODS, build_retriever

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "data" / "day6" / "questions.json"
ABSTAIN = ROOT / "data" / "day6" / "abstain.json"


def load_cases(split: str, include_abstain: bool) -> list[dict]:
    cases = [case for case in json.loads(QUESTIONS.read_text(encoding="utf-8")) if case["split"] == split]
    if include_abstain:
        cases += [case for case in json.loads(ABSTAIN.read_text(encoding="utf-8")) if case["split"] == split]
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description="Chạy agent Day 7 và ghi trace")
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0, help="chỉ chạy N câu đầu (0 = tất cả)")
    parser.add_argument("--include-abstain", action="store_true", help="thêm câu thiếu evidence")
    parser.add_argument("--max-searches", type=int, default=2)
    parser.add_argument("--max-steps", type=int, default=5)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--context-budget", type=int, default=4000)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=900)
    parser.add_argument("--scripted-demo", action="store_true", help="CHỈ kiểm tra đường ống, không phải kết quả")
    args = parser.parse_args()
    loaded = load_env()
    if loaded:
        print(f"loaded .env keys: {', '.join(loaded)}")

    cases = load_cases(args.split, args.include_abstain)
    if args.limit:
        cases = cases[: args.limit]
    if not cases:
        raise SystemExit("không có câu nào để chạy")

    retrievers = {name: build_retriever(name) for name in ("dense", "bm25", "hybrid")}
    tools = RetrievalTools(retrievers, top_k=args.top_k)
    for name in retrievers:
        if name not in set(METHODS):
            raise SystemExit(f"retriever lạ: {name}")

    if args.scripted_demo:
        controller = ScriptedController(
            [
                {"action": "search", "tool": "hybrid_search", "query": "placeholder"},
                {"action": "abstain", "reason": "scripted demo không trả lời"},
            ]
        )
        benchmark_result = False
        model_note = "scripted"
    else:
        try:
            model = model_from_env()
        except ProviderError as exc:
            raise SystemExit(f"không gọi được model: {exc}")
        except (ValueError, KeyError) as exc:
            raise SystemExit(
                "chưa cấu hình model. Đặt DAY7_LLM_PROVIDER / DAY7_LLM_MODEL / DAY7_LLM_API_KEY "
                f"(hoặc OPENAI_API_KEY). Chi tiết: {exc}"
            )
        controller = LLMController(model, temperature=args.temperature, max_tokens=args.max_tokens)
        benchmark_result = True
        model_note = getattr(model, "model", "unknown")

    started = time.perf_counter()
    traces = []
    for case in cases:
        result = run_agent(
            case["question"],
            controller,
            tools,
            filters=case.get("filter"),
            max_searches=args.max_searches,
            max_steps=args.max_steps,
            top_k=args.top_k,
            context_budget=args.context_budget,
            query_id=case["id"],
        )
        traces.append(result)
        print(f"{case['id']}: {result['status']:<9} searches={result['searches']} ctx={result['context_chars']}c")
    elapsed = time.perf_counter() - started

    status_counts: dict[str, int] = {}
    for trace in traces:
        status_counts[trace["status"]] = status_counts.get(trace["status"], 0) + 1
    usage_totals = {
        key: sum(int(trace["usage"].get(key) or 0) for trace in traces)
        for key in ("prompt_tokens", "completion_tokens")
    }

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "traces.json").write_text(json.dumps(traces, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.out / "cases.json").write_text(
        json.dumps(
            [
                {"id": case["id"], "split": case["split"], "answerable": case.get("answerable", True)}
                for case in cases
            ],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "benchmark_result": benchmark_result,
        "split": args.split,
        "model": model_note,
        "provider": getattr(getattr(controller, "model", None), "provider", None),
        "prompt_version": getattr(controller, "prompt_version", None),
        "params": {
            "max_searches": args.max_searches,
            "max_steps": args.max_steps,
            "top_k": args.top_k,
            "context_budget": args.context_budget,
            "temperature": args.temperature,
            "max_tokens": args.max_tokens,
            "tools": tools.names,
        },
        "cases": len(cases),
        "status_counts": status_counts,
        "usage": usage_totals,
        "cost_usd": None if not benchmark_result else 0.0,
        "cost_note": "Điền chi phí theo bảng giá provider; token ở trên là số đo thực tế.",
        "elapsed_seconds": round(elapsed, 2),
    }
    (args.out / "run_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
