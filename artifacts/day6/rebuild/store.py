"""Persistent Chroma vector store for strategies A and B.

C is evaluated against the B collection with a metadata filter; it does not get
its own collection. Keeping one index for B and C isolates the effect of the
filter.

Run from starter/:
    python -m src.store
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings

from .ingestion import load_corpus_jsonl
from .models import Chunk

ALLOWED_FILTERS = {"book"}


def _clean_metadata(chunk: Chunk) -> dict[str, Any]:
    metadata = {
        "strategy": str(chunk.metadata.get("strategy") or ""),
        "unit_id": str(chunk.metadata.get("unit_id") or ""),
        "book": int(chunk.metadata.get("book") or 0),
        "section": str(chunk.metadata.get("section") or ""),
        "chunk_index": int(chunk.metadata.get("chunk_index") or 0),
        "document_id": chunk.document_id,
        "source": chunk.source,
        "page": int(chunk.page),
    }
    return {key: value for key, value in metadata.items() if value is not None}


class ChromaStore:
    """Thin wrapper around a persistent Chroma client."""

    def __init__(
        self,
        path: str | Path = "results/chroma",
        dimensions: int = 384,
        *,
        prefix: str = "republic",
    ) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.dimensions = dimensions
        self.prefix = prefix
        self.client = chromadb.PersistentClient(
            path=str(self.path),
            settings=Settings(anonymized_telemetry=False),
        )

    def collection_name(self, strategy: str) -> str:
        if strategy not in {"A", "B"}:
            raise ValueError("strategy must be 'A' or 'B'")
        return f"{self.prefix}_{strategy}_{self.dimensions}"

    def reset(self, strategy: str) -> None:
        """Delete and recreate a strategy collection before a fresh ingest."""
        name = self.collection_name(strategy)
        try:
            self.client.delete_collection(name)
        except Exception:
            pass
        self.client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(
        self,
        strategy: str,
        chunks: list[Chunk],
        vectors: list[list[float]],
    ) -> None:
        if len(chunks) != len(vectors):
            raise ValueError(
                f"chunk/vector count mismatch: {len(chunks)} chunks, "
                f"{len(vectors)} vectors"
            )
        if not chunks:
            return
        for vector in vectors:
            if len(vector) != self.dimensions:
                raise ValueError(
                    f"vector dimension mismatch: expected {self.dimensions}, "
                    f"got {len(vector)}"
                )

        collection = self.client.get_or_create_collection(
            name=self.collection_name(strategy),
            metadata={"hnsw:space": "cosine"},
        )
        collection.upsert(
            ids=[chunk.chunk_id for chunk in chunks],
            embeddings=[list(vector) for vector in vectors],
            documents=[chunk.text for chunk in chunks],
            metadatas=[_clean_metadata(chunk) for chunk in chunks],
        )

    def count(self, strategy: str) -> int:
        return self.client.get_collection(self.collection_name(strategy)).count()

    def search(
        self,
        strategy: str,
        query_vector: list[float],
        top_k: int = 3,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        if len(query_vector) != self.dimensions:
            raise ValueError(
                f"query dimension mismatch: expected {self.dimensions}, "
                f"got {len(query_vector)}"
            )

        where: dict[str, Any] | None = None
        if filters:
            unknown = set(filters) - ALLOWED_FILTERS
            if unknown:
                raise ValueError(f"unsupported filters: {sorted(unknown)}")
            where = {key: value for key, value in filters.items()}

        collection = self.client.get_collection(self.collection_name(strategy))
        result = collection.query(
            query_embeddings=[list(query_vector)],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        hits: list[dict[str, Any]] = []
        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        for rank, (chunk_id, text, metadata, distance) in enumerate(
            zip(ids, documents, metadatas, distances),
            start=1,
        ):
            hits.append(
                {
                    "rank": rank,
                    "chunk_id": chunk_id,
                    "text": text,
                    "score": 1.0 - float(distance),
                    "distance": float(distance),
                    "metadata": metadata or {},
                }
            )
        return hits

    def close(self) -> None:
        """Chroma's persistent client does not need an explicit close."""
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a Chroma collection")
    parser.add_argument("--strategy", choices=["A", "B"], default="B")
    parser.add_argument("--path", default="results/chroma")
    args = parser.parse_args()

    store = ChromaStore(args.path, dimensions=384)
    print(f"path={store.path}")
    print(f"collection={store.collection_name(args.strategy)}")
    print(f"count={store.count(args.strategy)}")


if __name__ == "__main__":
    main()
