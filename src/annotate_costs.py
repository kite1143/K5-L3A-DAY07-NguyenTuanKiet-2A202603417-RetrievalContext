"""Ghi chi phí thực tế vào run_meta và chi phí từng câu vào costs.json.

`run_agent.py` chỉ ghi token; giá tiền phụ thuộc provider nên phải tính riêng và
ghi lại để người chấm đối chiếu được với báo cáo.

    python src/annotate_costs.py                      # mọi run có usage > 0
    python src/annotate_costs.py --price-in 0.15 --price-out 0.60

Giá mặc định là gpt-4o-mini (USD / 1M token). Run không có token (ví dụ
controller kịch bản) được bỏ qua và giữ `cost_usd: 0`.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "artifacts" / "day7" / "results"

DEFAULT_PRICE_IN = 0.15
DEFAULT_PRICE_OUT = 0.60


def compute(prompt_tokens: int, completion_tokens: int, price_in: float, price_out: float) -> float:
    return prompt_tokens / 1_000_000 * price_in + completion_tokens / 1_000_000 * price_out


def main() -> None:
    parser = argparse.ArgumentParser(description="Tính và ghi chi phí từ token đã dùng")
    parser.add_argument("--roots", nargs="*", type=Path, default=sorted(RESULTS.glob("agent-*")))
    parser.add_argument("--price-in", type=float, default=DEFAULT_PRICE_IN)
    parser.add_argument("--price-out", type=float, default=DEFAULT_PRICE_OUT)
    parser.add_argument("--model", default="gpt-4o-mini")
    args = parser.parse_args()

    rows = []
    for run in args.roots:
        meta_path = run / "run_meta.json"
        traces_path = run / "traces.json"
        if not meta_path.exists() or not traces_path.exists():
            print(f"bỏ qua {run.name}: thiếu run_meta.json hoặc traces.json")
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        traces = json.loads(traces_path.read_text(encoding="utf-8"))
        total_prompt = sum((t.get("usage") or {}).get("prompt_tokens") or 0 for t in traces)
        total_completion = sum((t.get("usage") or {}).get("completion_tokens") or 0 for t in traces)
        if total_prompt + total_completion == 0:
            print(f"bỏ qua {run.name}: không có token (run kịch bản)")
            continue

        per_query = []
        for trace in traces:
            usage = trace.get("usage") or {}
            prompt = int(usage.get("prompt_tokens") or 0)
            completion = int(usage.get("completion_tokens") or 0)
            per_query.append(
                {
                    "query_id": trace.get("query_id"),
                    "prompt_tokens": prompt,
                    "completion_tokens": completion,
                    "cost_usd": round(compute(prompt, completion, args.price_in, args.price_out), 6),
                    "latency_ms": trace.get("latency_ms"),
                }
            )

        total = compute(total_prompt, total_completion, args.price_in, args.price_out)
        payload = {
            "model": args.model,
            "price_usd_per_1m_tokens": {"input": args.price_in, "output": args.price_out},
            "prompt_tokens": total_prompt,
            "completion_tokens": total_completion,
            "total_usd": round(total, 6),
            "per_query": per_query,
        }
        (run / "costs.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        meta["cost_usd"] = round(total, 6)
        meta["cost_model"] = {
            "model": args.model,
            "price_usd_per_1m_tokens": {"input": args.price_in, "output": args.price_out},
            "computed_by": "src/annotate_costs.py",
        }
        meta["cost_note"] = "Tính từ token thực tế trong traces.json; chi tiết từng câu ở costs.json."
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        rows.append((run.name, total_prompt, total_completion, round(total, 4)))

    print(f"{'run':22s} {'prompt':>8s} {'completion':>11s} {'cost_usd':>9s}")
    for name, prompt, completion, total in rows:
        print(f"{name:22s} {prompt:>8d} {completion:>11d} {total:>9.4f}")
    print(f"tổng: {sum(row[3] for row in rows):.4f} USD")


if __name__ == "__main__":
    main()
