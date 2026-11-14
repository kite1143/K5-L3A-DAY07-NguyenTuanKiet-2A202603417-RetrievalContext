"""Evaluate retrieval traces against gold evidence.

A hit requires the retrieved chunk to come from the gold source/unit/page and
to contain the recorded evidence quote. The automatic metric deliberately does
not claim to measure LLM answer accuracy or human grounding.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any


def _normalize(text: str) -> str:
    return " ".join(str(text).split())


def evaluate_query(
    question: dict[str, Any],
    hits: list[dict[str, Any]],
    *,
    strategy: str,
    filter_applied: bool = False,
) -> dict[str, Any]:
    """Return one trace with per-hit match flags and Hit@1 / Evidence Hit@3."""
    if strategy not in {"A", "B", "C"}:
        raise ValueError("strategy must be A, B or C")

    gold_unit = question["gold_unit_id"]
    gold_source = question["gold_source_id"]
    gold_page = int(question["gold_page"])
    quote = _normalize(question["evidence_quote"])

    trace_hits: list[dict[str, Any]] = []
    for rank, hit in enumerate(hits, start=1):
        metadata = hit.get("metadata") or {}
        text = str(hit.get("text") or "")
        unit_match = metadata.get("unit_id") == gold_unit
        source_match = metadata.get("document_id") == gold_source
        page_match = int(metadata.get("page", -1)) == gold_page
        evidence_match = quote in _normalize(text)
        is_hit = unit_match and source_match and page_match and evidence_match

        trace_hits.append(
            {
                "rank": rank,
                "chunk_id": hit.get("chunk_id"),
                "text": text,
                "score": float(hit.get("score", 0.0)),
                "distance": hit.get("distance"),
                "metadata": metadata,
                "unit_match": unit_match,
                "source_match": source_match,
                "page_match": page_match,
                "evidence_match": evidence_match,
                "is_hit": is_hit,
            }
        )

    hit_at_1 = bool(trace_hits and trace_hits[0]["is_hit"])
    hit_at_3 = any(hit["is_hit"] for hit in trace_hits[:3])

    return {
        "strategy": strategy,
        "split": question["split"],
        "question_id": question["id"],
        "question": question["question"],
        "expected_answer": question["expected_answer"],
        "gold_source_id": gold_source,
        "gold_unit_id": gold_unit,
        "gold_page": gold_page,
        "gold_book": question.get("gold_book"),
        "filter": question.get("filter"),
        "filter_applied": bool(filter_applied),
        "evidence_quote": question["evidence_quote"],
        "hits": trace_hits,
        "hit_at_1": hit_at_1,
        "hit_at_3": hit_at_3,
    }


def _empty_bucket() -> dict[str, Any]:
    return {
        "n": 0,
        "hit1": 0,
        "hit3": 0,
        "filter_n": 0,
        "filter_hit1": 0,
        "filter_hit3": 0,
    }


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate counts by strategy and split, including filter-only counts."""
    buckets: dict[str, dict[str, dict[str, Any]]] = defaultdict(
        lambda: defaultdict(_empty_bucket)
    )

    for trace in traces:
        strategy = trace["strategy"]
        split = trace["split"]
        bucket = buckets[strategy][split]
        bucket["n"] += 1
        bucket["hit1"] += int(bool(trace["hit_at_1"]))
        bucket["hit3"] += int(bool(trace["hit_at_3"]))
        if trace.get("filter"):
            bucket["filter_n"] += 1
            bucket["filter_hit1"] += int(bool(trace["hit_at_1"]))
            bucket["filter_hit3"] += int(bool(trace["hit_at_3"]))

    result: dict[str, Any] = {}
    for strategy in sorted(buckets):
        result[strategy] = {}
        for split in ("dev", "test"):
            if split not in buckets[strategy]:
                continue
            bucket = dict(buckets[strategy][split])
            n = bucket["n"]
            bucket["hit1_rate"] = round(bucket["hit1"] / n, 4) if n else 0.0
            bucket["hit3_rate"] = round(bucket["hit3"] / n, 4) if n else 0.0
            result[strategy][split] = bucket
    return result
