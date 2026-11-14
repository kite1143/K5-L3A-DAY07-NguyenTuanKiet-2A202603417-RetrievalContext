"""Kiểm chứng vắng mặt cho các câu thiếu evidence (data/day6/abstain.json).

Mục đích: BENCHMARK.md yêu cầu không kết luận "thiếu bằng chứng" chỉ vì top-k
không tìm thấy. Script ghi lại bằng chứng kiểm tra cho từng câu:

  * lexical: TF-IDF trên 111 chunk Day 7, top-5 chunk gần nhất;
  * keyword: số lần xuất hiện của từng thuật ngữ chủ đề, kèm unit;
  * dense (tùy chọn): top-5 từ collection Chroma Day 6 (republic_B_384).

Kết quả ghi vào data/day6/abstain_checks.json để người chấm đối chiếu. Script
không tự phán "không trả lời được"; trường verdict vẫn do người làm bài đọc hit
rồi xác nhận.

Chạy từ thư mục gốc repo:

    python src/check_absence.py                # lexical + keyword
    python src/check_absence.py --no-dense     # bỏ qua dense
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHUNKS = ROOT / "data" / "day6" / "chunks.json"
ABSTAIN = ROOT / "data" / "day6" / "abstain.json"
OUTPUT = ROOT / "data" / "day6" / "abstain_checks.json"
CHROMA_PATH = ROOT / "artifacts" / "day6" / "chroma"
MODEL_CACHE = ROOT / "artifacts" / "day6" / "fastembed_cache"
COLLECTION = "republic_B_384"
SNIPPET = 260


def load_chunks() -> list[dict]:
    return json.loads(CHUNKS.read_text(encoding="utf-8"))


def lexical_rank(chunks: list[dict], question: str, top_k: int = 5) -> list[dict]:
    sys.path.insert(0, str(ROOT / "starter"))
    from baseline import TfidfIndex

    index = TfidfIndex(chunks)
    hits = index.search(question, top_k=top_k)
    return [
        {
            "chunk_id": hit["id"],
            "page": hit["page"],
            "book": hit["metadata"].get("book"),
            "score": round(float(hit["score"]), 4),
            "snippet": hit["text"][:SNIPPET],
        }
        for hit in hits
    ]


def keyword_scan(chunks: list[dict], terms: list[str], limit: int = 6) -> list[dict]:
    rows = []
    for term in terms:
        needle = term.casefold()
        units = [c["id"] for c in chunks if needle in c["text"].casefold()]
        rows.append({"term": term, "count": len(units), "units": units[:limit]})
    return rows


def dense_rank(question: str, top_k: int = 5) -> list[dict] | None:
    try:
        import chromadb
        from chromadb.config import Settings
        from fastembed import TextEmbedding
    except ImportError as exc:  # pragma: no cover - môi trường thiếu package
        return [{"error": f"thiếu package: {exc}"}]
    if not CHROMA_PATH.exists():
        return [{"error": f"không thấy store {CHROMA_PATH}"}]

    cache = str(MODEL_CACHE) if MODEL_CACHE.exists() else None
    model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5", cache_dir=cache)
    vector = next(iter(model.query_embed([question]))).tolist()

    client = chromadb.PersistentClient(
        path=str(CHROMA_PATH), settings=Settings(anonymized_telemetry=False)
    )
    collection = client.get_collection(COLLECTION)
    result = collection.query(
        query_embeddings=[vector],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )
    rows = []
    for chunk_id, text, metadata, distance in zip(
        result["ids"][0],
        result["documents"][0],
        result["metadatas"][0],
        result["distances"][0],
    ):
        rows.append(
            {
                "chunk_id": chunk_id,
                "unit_id": (metadata or {}).get("unit_id"),
                "page": (metadata or {}).get("page"),
                "cosine_similarity": round(1.0 - float(distance), 4),
                "snippet": text[:SNIPPET],
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Ghi bằng chứng kiểm chứng câu thiếu evidence")
    parser.add_argument("--dense", action="store_true", default=True)
    parser.add_argument("--no-dense", dest="dense", action="store_false")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    chunks = load_chunks()
    questions = json.loads(ABSTAIN.read_text(encoding="utf-8"))
    if not questions:
        raise ValueError("abstain.json rỗng")

    results = []
    for question in questions:
        lexical = lexical_rank(chunks, question["question"])
        keywords = keyword_scan(chunks, question.get("topic_terms", []))
        dense = dense_rank(question["question"]) if args.dense else None
        best_dense = None
        if dense and dense and "error" not in dense[0]:
            best_dense = dense[0]["cosine_similarity"]
        results.append(
            {
                "id": question["id"],
                "split": question["split"],
                "question": question["question"],
                "best_lexical_score": lexical[0]["score"] if lexical else 0.0,
                "best_dense_cosine": best_dense,
                "lexical_top5": lexical,
                "dense_top5": dense,
                "keyword_scan": keywords,
                "keyword_terms_present": [row["term"] for row in keywords if row["count"]],
                "manual_verdict": question.get("absence_reason"),
                "reviewed_hits": question.get("near_topic_units", []),
            }
        )
        dense_note = f"{best_dense:.3f}" if best_dense is not None else "n/a"
        print(
            f"{question['id']} ({question['split']}): lexical={lexical[0]['score']:.3f} "
            f"dense={dense_note} keyword_hits={[r['term'] for r in keywords if r['count']]}"
        )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generated_by": "src/check_absence.py",
        "purpose": (
            "Bằng chứng kiểm tra vắng mặt: top-5 lexical, top-5 dense và số lần xuất hiện "
            "thuật ngữ chủ đề. Không dùng top-k miss làm kết luận duy nhất."
        ),
        "corpus_chunks": len(chunks),
        "store": {"path": str(CHROMA_PATH.relative_to(ROOT)), "collection": COLLECTION},
        "dense_enabled": bool(args.dense),
        "results": results,
    }
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {args.output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
