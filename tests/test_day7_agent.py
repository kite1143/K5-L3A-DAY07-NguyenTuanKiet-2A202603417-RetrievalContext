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


class ToolErrorTests(unittest.TestCase):
    class FakeRetriever:
        method = "fake"

        def search(self, query, *, top_k=3, filters=None):
            return [hit("a")]

    def test_unknown_tool_is_rejected(self):
        from agent.tools import RetrievalTools, ToolError

        tools = RetrievalTools({"hybrid": self.FakeRetriever()})
        with self.assertRaises(ToolError):
            tools.run("web_search", "q", filters=None)

    def test_empty_query_is_rejected(self):
        from agent.tools import RetrievalTools, ToolError

        tools = RetrievalTools({"hybrid": self.FakeRetriever()})
        with self.assertRaises(ToolError):
            tools.run("hybrid_search", "   ", filters=None)

    def test_top_k_bounds_are_enforced(self):
        from agent.tools import RetrievalTools, ToolError

        tools = RetrievalTools({"hybrid": self.FakeRetriever()}, max_top_k=5)
        with self.assertRaises(ToolError):
            tools.run("hybrid_search", "q", filters=None, top_k=99)

    def test_tool_failure_becomes_error_status(self):
        from agent.tools import RetrievalTools, ToolError

        class Broken(RetrievalTools):
            def run(self, name, query, *, filters, top_k=None):
                raise ToolError("vector store offline")

        controller = ScriptedController([{"action": "search", "tool": "hybrid_search", "query": "q"}])
        result = run_agent("Q?", controller, Broken({}), query_id="q6")
        self.assertEqual(result["status"], "error")
        self.assertIn("vector store offline", result["error"])


class RepairTests(unittest.TestCase):
    def test_broken_json_is_repaired_once(self):
        from agent.controller import LLMController

        class FlakyModel:
            provider = "fake"
            model = "fake"

            def __init__(self):
                self.calls = 0

            def chat(self, messages, *, temperature=0.0, max_tokens=900):
                self.calls += 1
                if self.calls == 1:
                    return {"text": '{"action": "search", "query": "x")', "usage": {"prompt_tokens": 10}}
                return {"text": '{"action": "abstain", "reason": "none"}', "usage": {"prompt_tokens": 5}}

        model = FlakyModel()
        controller = LLMController(model, repair_attempts=1)
        result = controller.decide("Q?", [])
        self.assertEqual(result.action["action"], "abstain")
        self.assertEqual(model.calls, 2)
        self.assertEqual(result.usage["prompt_tokens"], 15)

    def test_repair_gives_up_after_limit(self):
        from agent.controller import LLMController

        class BadModel:
            provider = "fake"
            model = "fake"

            def chat(self, messages, *, temperature=0.0, max_tokens=900):
                return {"text": "not json at all", "usage": {}}

        controller = LLMController(BadModel(), repair_attempts=0)
        with self.assertRaises(ControllerError):
            controller.decide("Q?", [])


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
