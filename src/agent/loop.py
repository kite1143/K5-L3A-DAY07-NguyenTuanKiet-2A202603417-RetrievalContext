"""Vòng lặp agent: model thật + tool retrieval + trace, có citation và abstention.

Không có gold trong vòng lặp này. Mọi lỗi provider/tool được ghi thành
status='error' kèm thông điệp, không thay bằng câu trả lời giả.
"""
from __future__ import annotations

import time
from typing import Any

from retrieval.context import DEFAULT_BUDGET, pack_context

from .controller import ControllerError, LLMController
from .tools import ToolError

ABSTAIN_TEXT = "Không đủ bằng chứng trong tài liệu để trả lời câu hỏi này."


def _context_from_candidates(
    candidates: list[dict], budget: int, query: str | None, block_cap: int | None
) -> tuple[str, list[str]]:
    return pack_context(candidates, budget=budget, query=query, block_cap=block_cap)


def run_agent(
    question: str,
    controller: LLMController,
    tools,
    *,
    filters: dict | None = None,
    max_searches: int = 3,
    max_steps: int = 6,
    top_k: int = 5,
    context_budget: int = DEFAULT_BUDGET,
    context_block_cap: int | None = None,
    query_id: str | None = None,
) -> dict[str, Any]:
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question phải là chuỗi không rỗng")
    if max_searches < 1 or max_steps < 1 or top_k < 1 or context_budget < 1:
        raise ValueError("tham số vòng lặp không hợp lệ")

    started = time.perf_counter()
    history: list[dict] = []
    candidates: list[dict] = []
    seen: set[str] = set()
    events: list[dict] = []
    usage = {"prompt_tokens": 0, "completion_tokens": 0}
    model = getattr(controller, "model", None)

    def finish(status: str, answer: str, citations: list[str], extra: dict | None = None) -> dict:
        result = {
            "query_id": query_id,
            "question": question,
            "filter": filters,
            "status": status,
            "answer": answer,
            "citations": citations,
            "events": events,
            "context_chars": len(history[-1]["context"]) if history else 0,
            "context_ids": history[-1]["context_ids"] if history else [],
            "searches": sum(1 for e in events if e["event"] == "search"),
            "usage": usage,
            "model": getattr(model, "model", None) if model else None,
            "provider": getattr(model, "provider", None) if model else None,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "prompt_version": getattr(controller, "prompt_version", None),
        }
        if extra:
            result.update(extra)
        return result

    for step in range(1, max_steps + 1):
        try:
            decision = controller.decide(question, history, filters=filters)
        except ControllerError as exc:
            events.append({"event": "error", "stage": "parse", "step": step, "message": str(exc)})
            return finish("error", "", [], {"error": str(exc)})
        except Exception as exc:  # provider/network error
            events.append({"event": "error", "stage": "provider", "step": step, "message": str(exc)})
            return finish("error", "", [], {"error": str(exc)})

        for key in ("prompt_tokens", "completion_tokens"):
            value = (decision.usage or {}).get(key)
            if isinstance(value, int):
                usage[key] += value

        action = decision.action
        action_type = action.get("action")

        if action_type == "search":
            if sum(1 for e in events if e["event"] == "search") >= max_searches:
                events.append({"event": "search_limit", "step": step})
                return finish("abstain", ABSTAIN_TEXT, [], {"reason": "search_limit"})
            tool = action.get("tool") or "hybrid_search"
            query = action["query"]
            started_search = time.perf_counter()
            try:
                hits = tools.run(tool, query, filters=filters, top_k=top_k)
            except ToolError as exc:
                events.append({"event": "tool_error", "tool": tool, "query": query, "message": str(exc)})
                return finish("error", "", [], {"error": str(exc)})
            search_ms = (time.perf_counter() - started_search) * 1000
            new_hits = [hit for hit in hits if hit["id"] not in seen]
            for hit in hits:
                if hit["id"] not in seen:
                    seen.add(hit["id"])
                    candidates.append(hit)
            search_log = " ".join(entry["query"] for entry in history if entry.get("query"))
            context, context_ids = _context_from_candidates(
                candidates, context_budget, search_log or question, context_block_cap
            )
            entry = {
                "tool": tool,
                "query": query,
                "results": [
                    {"id": hit["id"], "page": hit.get("page"), "score": hit.get("score"), "rank": hit.get("rank")}
                    for hit in hits
                ],
                "new_ids": [hit["id"] for hit in new_hits],
                "context": context,
                "context_ids": context_ids,
                "filter": filters,
                "latency_ms": round(search_ms, 2),
                "model_latency_ms": round(decision.latency_ms, 2),
            }
            history.append(entry)
            events.append({"event": "search", **entry})
        elif action_type == "answer":
            answer = action["answer"]
            citations = action.get("citations") or []
            valid_ids = set(history[-1]["context_ids"]) if history else set()
            ok = bool(
                answer.strip()
                and citations
                and all(citation in valid_ids for citation in citations)
                and all(f"[{citation}]" in answer for citation in citations)
            )
            events.append(
                {
                    "event": "answer",
                    "step": step,
                    "raw": decision.raw_text[:2000],
                    "citations": citations,
                    "citations_in_context": [c for c in citations if c in valid_ids],
                    "model_latency_ms": round(decision.latency_ms, 2),
                }
            )
            if ok:
                return finish("answered", answer, citations)
            return finish("abstain", ABSTAIN_TEXT, [], {"reason": "invalid_or_missing_citations"})
        else:
            reason = action.get("reason") or "model_abstained"
            events.append(
                {
                    "event": "abstain",
                    "step": step,
                    "reason": reason,
                    "raw": decision.raw_text[:2000],
                    "model_latency_ms": round(decision.latency_ms, 2),
                }
            )
            return finish("abstain", ABSTAIN_TEXT, [], {"reason": reason})

    events.append({"event": "step_limit", "step": max_steps})
    return finish("abstain", ABSTAIN_TEXT, [], {"reason": "step_limit"})
