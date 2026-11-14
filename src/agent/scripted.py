"""Controller kịch bản — CHỈ dùng để test code, không dùng cho kết quả benchmark.

Starter Day 7 cũng ghi rõ: mock chỉ dùng để kiểm tra code, không báo cáo chất
lượng. Mọi run dùng file này đều được đánh dấu `benchmark_result = false`.
"""
from __future__ import annotations

from .controller import ControllerResult


class ScriptedController:
    prompt_version = "scripted-demo"

    def __init__(self, script: list[dict]) -> None:
        if not script:
            raise ValueError("script rỗng")
        self.script = list(script)
        self.calls = 0
        self.model = type("MockModel", (), {"model": "scripted", "provider": "scripted"})()

    def decide(self, question: str, history: list[dict], *, filters: dict | None = None) -> ControllerResult:
        index = min(self.calls, len(self.script) - 1)
        action = self.script[index]
        self.calls += 1
        return ControllerResult(action=dict(action), usage={}, latency_ms=0.0, raw_text='{"scripted": true}')


def scripted_policy(script: list[dict]):
    return ScriptedController(script)
