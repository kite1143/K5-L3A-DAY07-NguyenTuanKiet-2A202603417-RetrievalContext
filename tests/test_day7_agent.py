"""Kiểm tra vòng lặp agent bằng controller kịch bản (không dùng cho metric)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.controller import ControllerError, parse_action
from agent.loop import run_agent
from agent.scripted import ScriptedController


def hit(chunk_id, text="passage", page=1):
    return {
        "id": chunk_id,
        "text": text,
        "source_id": "doc",
        "source": "example://doc",
        "page": page,
        "metadata": {"book": 1},
        "score": 1.0,
        "rank": 1,
    }


class FakeTools:
    names = ["hybrid_search"]

    def __init__(self, hits):
        self.hits = hits
        self.calls = []

    def run(self, name, query, *, filters, top_k=None):
        self.calls.append((name, query, filters))
        return list(self.hits)


class ParseTests(unittest.TestCase):
    def test_plain_json(self):
        action = parse_action('{"action": "search", "query": "justice"}')
        self.assertEqual(action["action"], "search")

    def test_fenced_json(self):
        action = parse_action('Here you go:\n```json\n{"action": "abstain", "reason": "none"}\n```')
        self.assertEqual(action["action"], "abstain")

    def test_rejects_unknown_action(self):
        with self.assertRaises(ControllerError):
            parse_action('{"action": "hallucinate"}')

    def test_rejects_search_without_query(self):
        with self.assertRaises(ControllerError):
            parse_action('{"action": "search"}')


class LoopTests(unittest.TestCase):
    def test_answer_with_valid_citation(self):
        controller = ScriptedController(
            [
                {"action": "search", "tool": "hybrid_search", "query": "justice"},
                {"action": "answer", "answer": "Justice is paying debts [a].", "citations": ["a"]},
            ]
        )
        result = run_agent("What is justice?", controller, FakeTools([hit("a")]), query_id="q1")
        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["citations"], ["a"])
        self.assertEqual(result["searches"], 1)

    def test_citation_outside_context_abstains(self):
        controller = ScriptedController(
            [
                {"action": "search", "tool": "hybrid_search", "query": "justice"},
                {"action": "answer", "answer": "Invented [zz].", "citations": ["zz"]},
            ]
        )
        result = run_agent("What is justice?", controller, FakeTools([hit("a")]), query_id="q2")
        self.assertEqual(result["status"], "abstain")
        self.assertEqual(result["reason"], "invalid_or_missing_citations")

    def test_missing_marker_in_answer_abstains(self):
        controller = ScriptedController(
            [
                {"action": "search", "tool": "hybrid_search", "query": "justice"},
                {"action": "answer", "answer": "Justice is paying debts.", "citations": ["a"]},
            ]
        )
        result = run_agent("What is justice?", controller, FakeTools([hit("a")]), query_id="q3")
        self.assertEqual(result["status"], "abstain")

    def test_search_limit_abstains(self):
        controller = ScriptedController([{"action": "search", "tool": "hybrid_search", "query": "x"}])
        result = run_agent("Q?", controller, FakeTools([hit("a")]), max_searches=2, query_id="q4")
        self.assertEqual(result["status"], "abstain")
        self.assertEqual(result["reason"], "search_limit")
        self.assertEqual(len(controller.script), 1)

    def test_provider_failure_is_recorded_not_hidden(self):
        class Boom:
            prompt_version = "boom"

            class model:  # noqa: N801 - giả lập adapter
                model = "boom"
                provider = "boom"

            def decide(self, question, history, *, filters=None):
                raise RuntimeError("connection refused")

        result = run_agent("Q?", Boom(), FakeTools([hit("a")]), query_id="q5")
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["events"][-1]["stage"], "provider")
        self.assertIn("connection refused", result["error"])


if __name__ == "__main__":
    unittest.main()
