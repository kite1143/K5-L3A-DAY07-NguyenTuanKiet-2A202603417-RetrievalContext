"""Dense retrieval trên vector store Chroma, dùng đúng embedding model Day 6.

Index Day 7 là view cấp unit của corpus Day 6: 111 chunk, cùng model
BAAI/bge-small-en-v1.5 (384 chiều, cosine) nên query embedding tương thích
tuyệt đối với index. Collection Day 6 (republic_B_384) vẫn dùng để đối chứng
chunking ở `ablation_day6_b`.
"""
from __future__ import annotations

import math
from pathlib import Path

import chromadb
from chromadb.config import Settings

MODEL_NAME = "BAAI/bge-small-en-v1.5"
DIMENSIONS = 384
DEFAULT_COLLECTION = "day7_units_384"
DAY6_COLLECTION = "republic_B_384"


def normalize(vector) -> list[float]:
    # fastembed trả numpy.float32; Chroma chỉ nhận float Python thuần.
    values = [float(value) for value in vector]
    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0:
        raise ValueError("embedding model trả vector 0")
    return [value / norm for value in values]


class Embedder:
    """Bọc fastembed để dùng chung model/cache với Day 6."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        from fastembed import TextEmbedding

        kwargs = {"model_name": MODEL_NAME}
        if cache_dir is not None and Path(cache_dir).exists():
            kwargs["cache_dir"] = str(cache_dir)
        self.model = TextEmbedding(**kwargs)
        self.model_name = MODEL_NAME
        self.dimensions = DIMENSIONS

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = [normalize(list(vector)) for vector in self.model.passage_embed(texts)]
        for vector in vectors:
            if len(vector) != DIMENSIONS:
                raise ValueError(f"vector {len(vector)} chiều, cần {DIMENSIONS}")
        return vectors

    def embed_query(self, question: str) -> list[float]:
        vector = normalize(list(next(iter(self.model.query_embed([question])))))
        if len(vector) != DIMENSIONS:
            raise ValueError(f"query vector {len(vector)} chiều, cần {DIMENSIONS}")
        return vector


class DenseStore:
    def __init__(self, path: Path, collection: str = DEFAULT_COLLECTION) -> None:
        self.path = Path(path)
        self.collection_name = collection
        self.client = chromadb.PersistentClient(
            path=str(self.path), settings=Settings(anonymized_telemetry=False)
        )

    def drop(self) -> None:
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            pass

    def build(self, chunks: list[dict], embedder: Embedder, *, batch_size: int = 32) -> int:
        self.drop()
        collection = self.client.get_or_create_collection(
            self.collection_name, metadata={"hnsw:space": "cosine"}
        )
        ids, texts, metadatas = [], [], []
        for chunk in chunks:
            metadata = chunk["metadata"]
            ids.append(chunk["id"])
            texts.append(chunk["text"])
            metadatas.append(
                {
                    "unit_id": chunk["id"],
                    "book": int(metadata.get("book") or 0),
                    "section": str(metadata.get("section") or ""),
                    "page": int(chunk["page"]),
                    "source_id": chunk["source_id"],
                    "source": chunk["source"],
                }
            )
        for start in range(0, len(texts), batch_size):
            stop = start + batch_size
            vectors = embedder.embed_documents(texts[start:stop])
            collection.upsert(
                ids=ids[start:stop],
                embeddings=vectors,
                documents=texts[start:stop],
                metadatas=metadatas[start:stop],
            )
        return collection.count()

    def search(
        self,
        query_vector: list[float],
        *,
        top_k: int = 3,
        filters: dict | None = None,
    ) -> list[dict]:
        if top_k <= 0:
            raise ValueError("top_k phải > 0")
        if len(query_vector) != DIMENSIONS:
            raise ValueError(f"query vector phải {DIMENSIONS} chiều")
        collection = self.client.get_collection(self.collection_name)
        where = None
        if filters:
            unknown = set(filters) - {"book"}
            if unknown:
                raise ValueError(f"filter không hỗ trợ: {sorted(unknown)}")
            where = {key: value for key, value in filters.items() if value is not None}
        result = collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            where=where or None,
            include=["documents", "metadatas", "distances"],
        )
        hits = []
        for rank, (chunk_id, text, metadata, distance) in enumerate(
            zip(
                result["ids"][0],
                result["documents"][0],
                result["metadatas"][0],
                result["distances"][0],
            ),
            start=1,
        ):
            metadata = metadata or {}
            hits.append(
                {
                    "id": chunk_id,
                    "text": text,
                    "source_id": metadata.get("source_id"),
                    "source": metadata.get("source"),
                    "page": metadata.get("page"),
                    "metadata": {
                        "unit_id": metadata.get("unit_id"),
                        "book": metadata.get("book"),
                        "section": metadata.get("section"),
                        "page": metadata.get("page"),
                        "source_id": metadata.get("source_id"),
                    },
                    "score": round(1.0 - float(distance), 6),
                    "rank": rank,
                }
            )
        return hits


class DenseRetriever:
    method = "dense"

    def __init__(self, store: DenseStore, embedder: Embedder) -> None:
        self.store = store
        self.embedder = embedder

    def search(self, query: str, *, top_k: int = 3, filters: dict | None = None) -> list[dict]:
        vector = self.embedder.embed_query(query)
        return self.store.search(vector, top_k=top_k, filters=filters)
