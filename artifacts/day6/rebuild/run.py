"""Run the Day 06 A/B/C retrieval pipeline.

A: fixed-size chunks, no filter.
B: paragraph chunks, no filter.
C: the same B index, with a metadata filter only when the question supplies one.

Run from starter/:
    python -m src.run --smoke
    python -m src.run
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .chunking import (
    FIXED_OVERLAP,
    FIXED_SIZE,
    PARAGRAPH_MAX,
    PARAGRAPH_MAX_OVERSHOOT,
    PARAGRAPH_MIN,
    build_chunks,
    chunk_stats,
)
from .embeddings import DEFAULT_DIMENSIONS, DEFAULT_MODEL, MyEmbedder
from .evaluation import evaluate_query, summarize
from .ingestion import DEFAULT_CORPUS, load_corpus_jsonl
from .store import ChromaStore

STARTER = Path(__file__).resolve().parents[1]
ROOT = STARTER.parent
DEFAULT_BENCHMARK = ROOT / "benchmark" / "questions.jsonl"
DEFAULT_BENCHMARK_MANIFEST = ROOT / "benchmark" / "manifest.json"
DEFAULT_RESULTS = STARTER / "results"

load_dotenv(STARTER / ".env")


def _default_chroma_path() -> Path:
    configured = Path(os.getenv("CHROMA_PATH", "results/chroma"))
    return configured if configured.is_absolute() else STARTER / configured


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load_questions(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"benchmark not found: {path}")
    questions = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(questions) < 20:
        raise ValueError(f"benchmark has {len(questions)} questions; need 20")
    required = {
        "id",
        "split",
        "question",
        "expected_answer",
        "gold_source_id",
        "gold_page",
        "gold_unit_id",
        "gold_book",
        "evidence_quote",
        "filter",
    }
    for question in questions:
        missing = required - set(question)
        if missing:
            raise ValueError(f"{question.get('id')} missing fields: {sorted(missing)}")
        if question["split"] not in {"dev", "test"}:
            raise ValueError(f"{question['id']} has invalid split")
        if question["filter"] is not None:
            if set(question["filter"]) != {"book"}:
                raise ValueError(f"{question['id']} has an invalid filter")
    return questions


def _check_frozen_files(corpus_path: Path, benchmark_path: Path) -> None:
    manifest_path = DEFAULT_BENCHMARK_MANIFEST
    if not manifest_path.is_file():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    questions_hash = sha256_file(benchmark_path)
    corpus_hash = sha256_file(corpus_path)
    if manifest.get("questions_sha256") != questions_hash:
        raise ValueError("benchmark questions.jsonl does not match its frozen manifest")
    if manifest.get("corpus_sha256") != corpus_hash:
        raise ValueError("data/corpus.jsonl does not match the frozen benchmark manifest")


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_summary(path: Path, metrics: dict[str, Any], *, label: str) -> None:
    lines = [
        f"# Retrieval summary ({label})",
        "",
        "| Strategy | Split | Hit@1 | Evidence Hit@3 | n | Filter n | Filter Hit@3 |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for strategy in ("A", "B", "C"):
        for split in ("dev", "test"):
            bucket = metrics.get(strategy, {}).get(split)
            if not bucket:
                continue
            lines.append(
                f"| {strategy} | {split} | {bucket['hit1']}/{bucket['n']} "
                f"({bucket['hit1_rate']:.1%}) | {bucket['hit3']}/{bucket['n']} "
                f"({bucket['hit3_rate']:.1%}) | {bucket['n']} | "
                f"{bucket['filter_n']} | {bucket['filter_hit3']}/{bucket['filter_n']} |"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Day 06 retrieval benchmark")
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    parser.add_argument("--benchmark", default=str(DEFAULT_BENCHMARK))
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS))
    parser.add_argument("--chroma", default=str(_default_chroma_path()))
    parser.add_argument("--model", default=os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL))
    parser.add_argument(
        "--dimensions",
        type=int,
        default=int(os.getenv("EMBEDDING_DIM", str(DEFAULT_DIMENSIONS))),
    )
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--smoke", action="store_true", help="run only 3 dev questions")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--no-reset", action="store_true")
    args = parser.parse_args()

    corpus_path = Path(args.corpus)
    benchmark_path = Path(args.benchmark)
    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    _check_frozen_files(corpus_path, benchmark_path)

    pages = load_corpus_jsonl(corpus_path)
    questions = load_questions(benchmark_path)
    if args.smoke:
        selected = [q for q in questions if q["split"] == "dev"][:3]
        label = "smoke"
    elif args.limit:
        selected = questions[: args.limit]
        label = f"limit-{args.limit}"
    else:
        selected = questions
        label = "full"
    if not selected:
        raise ValueError("no questions selected")

    print(f"corpus_pages={len(pages)} questions={len(questions)} selected={len(selected)}")

    chunks_a = build_chunks(pages, "A")
    chunks_b = build_chunks(pages, "B")
    if not chunks_a or not chunks_b:
        raise RuntimeError("chunking produced no chunks")
    print(f"chunks A={len(chunks_a)} B={len(chunks_b)} C={len(chunks_b)}")

    embedder = MyEmbedder(
        args.model,
        args.dimensions,
        batch_size=args.batch_size,
    )
    dimensions = int(embedder.dimensions or args.dimensions)

    ingest_start = time.perf_counter()
    vectors_a = embedder.embed_documents([chunk.text for chunk in chunks_a])
    vectors_b = embedder.embed_documents([chunk.text for chunk in chunks_b])
    embed_seconds = time.perf_counter() - ingest_start

    store = ChromaStore(args.chroma, dimensions)
    if not args.no_reset:
        store.reset("A")
        store.reset("B")
    store.upsert("A", chunks_a, vectors_a)
    store.upsert("B", chunks_b, vectors_b)
    count_a = store.count("A")
    count_b = store.count("B")
    if count_a != len(chunks_a) or count_b != len(chunks_b):
        raise RuntimeError(
            f"store count mismatch: A {count_a}/{len(chunks_a)}, "
            f"B {count_b}/{len(chunks_b)}"
        )
    print(f"store counts A={count_a} B={count_b} path={store.path}")

    query_start = time.perf_counter()
    traces: list[dict[str, Any]] = []
    for index, question in enumerate(selected, start=1):
        query_vector = embedder.embed_query(question["question"])
        hits_a = store.search("A", query_vector, top_k=args.top_k)
        hits_b = store.search("B", query_vector, top_k=args.top_k)
        filter_value = question.get("filter")
        if filter_value:
            hits_c = store.search("B", query_vector, top_k=args.top_k, filters=filter_value)
            filter_applied = True
        else:
            hits_c = store.search("B", query_vector, top_k=args.top_k)
            filter_applied = False

        traces.append(evaluate_query(question, hits_a, strategy="A"))
        traces.append(evaluate_query(question, hits_b, strategy="B"))
        traces.append(
            evaluate_query(
                question,
                hits_c,
                strategy="C",
                filter_applied=filter_applied,
            )
        )
        print(f"query {index}/{len(selected)} {question['id']} done")
    query_seconds = time.perf_counter() - query_start

    metrics = summarize(traces)
    stats_a = chunk_stats(chunks_a)
    stats_b = chunk_stats(chunks_b)
    chunk_stats_payload = {
        "A": stats_a,
        "B": stats_b,
        "C": {**stats_b, "shared_index_with": "B"},
    }

    now = datetime.now(timezone.utc).isoformat()
    config = {
        "run_label": label,
        "created_at": now,
        "corpus": {
            "path": str(corpus_path),
            "sha256": sha256_file(corpus_path),
            "pages": len(pages),
        },
        "benchmark": {
            "path": str(benchmark_path),
            "sha256": sha256_file(benchmark_path),
            "questions": len(questions),
            "selected": len(selected),
            "dev_selected": sum(1 for q in selected if q["split"] == "dev"),
            "test_selected": sum(1 for q in selected if q["split"] == "test"),
        },
        "embedding": {
            "provider": embedder.provider,
            "model": embedder.model_name,
            "dimensions": dimensions,
            "batch_size": args.batch_size,
            "normalized": True,
        },
        "store": {
            "backend": "chroma",
            "path": str(store.path),
            "collections": {
                "A": store.collection_name("A"),
                "B": store.collection_name("B"),
                "C": store.collection_name("B"),
            },
            "metric": "cosine",
            "retrieval_strategy": {"A": "A", "B": "B", "C": "B"},
            "filter_policy": "C applies book only when question.filter is present; A/B never filter.",
        },
        "chunking": {
            "A": {"type": "fixed_size", "size": FIXED_SIZE, "overlap": FIXED_OVERLAP},
            "B": {
                "type": "paragraph",
                "max_target": PARAGRAPH_MAX,
                "min_target": PARAGRAPH_MIN,
                "max_overshoot": PARAGRAPH_MAX_OVERSHOOT,
            },
            "C": "same segments as B",
        },
        "chunk_counts": {"A": len(chunks_a), "B": len(chunks_b), "C": len(chunks_b)},
        "top_k": args.top_k,
        "counts": {"A": count_a, "B": count_b},
        "timing_seconds": {
            "embedding": round(embed_seconds, 3),
            "queries": round(query_seconds, 3),
            "total": round(embed_seconds + query_seconds, 3),
        },
        "cost_usd": 0.0,
        "cost_note": "Local FastEmbed model; no paid API calls.",
    }

    prefix = "smoke_" if args.smoke else ""
    traces_path = results_dir / f"{prefix}traces.jsonl"
    metrics_path = results_dir / f"{prefix}metrics.json"
    config_path = results_dir / f"{prefix}run_config.json"
    stats_path = results_dir / f"{prefix}chunk_stats.json"
    summary_path = results_dir / f"{prefix}summary.md"
    per_question_path = results_dir / f"{prefix}per_question.csv"

    with traces_path.open("w", encoding="utf-8") as handle:
        for trace in traces:
            handle.write(json.dumps(trace, ensure_ascii=False) + "\n")
    _write_json(metrics_path, metrics)
    _write_json(config_path, config)
    _write_json(stats_path, chunk_stats_payload)
    _write_summary(summary_path, metrics, label=label)

    with per_question_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "strategy",
                "split",
                "question_id",
                "hit_at_1",
                "hit_at_3",
                "filter_applied",
                "top1_chunk_id",
                "top1_unit_id",
                "top1_score",
            ]
        )
        for trace in traces:
            top1 = trace["hits"][0] if trace["hits"] else {}
            writer.writerow(
                [
                    trace["strategy"],
                    trace["split"],
                    trace["question_id"],
                    int(trace["hit_at_1"]),
                    int(trace["hit_at_3"]),
                    int(trace["filter_applied"]),
                    top1.get("chunk_id", ""),
                    top1.get("metadata", {}).get("unit_id", ""),
                    top1.get("score", ""),
                ]
            )

    print(f"wrote {traces_path}")
    print(f"wrote {metrics_path}")
    print(f"wrote {config_path}")
    _write_console_summary(metrics, label)


def _write_console_summary(metrics: dict[str, Any], label: str) -> None:
    print(f"\nMETRICS ({label})")
    print("strategy split n hit1 hit3 filter_n filter_hit3")
    for strategy in ("A", "B", "C"):
        for split in ("dev", "test"):
            bucket = metrics.get(strategy, {}).get(split)
            if not bucket:
                continue
            print(
                f"{strategy} {split:4} {bucket['n']:2} {bucket['hit1']:2} "
                f"{bucket['hit3']:2} {bucket['filter_n']:2} {bucket['filter_hit3']:2}"
            )


if __name__ == "__main__":
    main()
