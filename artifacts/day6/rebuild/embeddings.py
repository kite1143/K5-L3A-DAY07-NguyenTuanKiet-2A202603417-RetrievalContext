"""Real local embedding adapter backed by FastEmbed.

Run from starter/:
    python -m src.embeddings
"""
from __future__ import annotations

import argparse
import math
import os
from pathlib import Path
from typing import Protocol, Sequence

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_DIMENSIONS = 384


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""
        ...

    def embed_query(self, question: str) -> list[float]:
        """Return a query vector compatible with the stored document vectors."""
        ...


def _normalize(vector: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        raise ValueError("embedding model returned a zero vector")
    return [value / norm for value in vector]


class MyEmbedder:
    """FastEmbed-backed embedder with an explicit model and dimension check."""

    provider = "fastembed"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        dimensions: int | None = DEFAULT_DIMENSIONS,
        *,
        cache_dir: str | Path | None = None,
        batch_size: int = 32,
    ) -> None:
        if not model_name.strip():
            raise ValueError("model_name must not be empty")
        if dimensions is not None and dimensions <= 0:
            raise ValueError("dimensions must be positive")
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")

        self.model_name = model_name
        self.dimensions = dimensions
        self.batch_size = batch_size

        try:
            from fastembed import TextEmbedding
        except ImportError as exc:
            raise RuntimeError(
                "fastembed is not installed; run "
                "'python -m pip install -r requirements.local.txt'"
            ) from exc

        kwargs: dict[str, object] = {"model_name": model_name}
        if cache_dir is not None:
            kwargs["cache_dir"] = str(cache_dir)
        try:
            self.model = TextEmbedding(**kwargs)
        except Exception as exc:
            raise RuntimeError(
                f"cannot initialize embedding model {model_name!r}: {exc}"
            ) from exc

    def _check_dimensions(self, vector: list[float]) -> None:
        if self.dimensions is None:
            self.dimensions = len(vector)
        elif len(vector) != self.dimensions:
            raise ValueError(
                f"embedding dimension mismatch: expected {self.dimensions}, "
                f"got {len(vector)} from {self.model_name}"
            )

    def _embed(self, texts: list[str], *, query: bool) -> list[list[float]]:
        if not texts:
            return []
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise ValueError("texts must be non-empty strings")

        method = self.model.query_embed if query else self.model.passage_embed
        try:
            raw_vectors = list(method(texts, batch_size=self.batch_size))
        except Exception as exc:
            raise RuntimeError(
                f"embedding failed for model {self.model_name!r}: {exc}"
            ) from exc

        vectors: list[list[float]] = []
        for raw in raw_vectors:
            vector = raw.tolist() if hasattr(raw, "tolist") else list(raw)
            vector = [float(value) for value in vector]
            self._check_dimensions(vector)
            vectors.append(_normalize(vector))

        if len(vectors) != len(texts):
            raise RuntimeError(
                f"model returned {len(vectors)} vectors for {len(texts)} texts"
            )
        return vectors

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, query=False)

    def embed_query(self, question: str) -> list[float]:
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be a non-empty string")
        return self._embed([question], query=True)[0]

    def info(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "model_name": self.model_name,
            "dimensions": self.dimensions,
            "batch_size": self.batch_size,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Check the local embedding model")
    parser.add_argument(
        "--model",
        default=os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL),
    )
    parser.add_argument(
        "--dimensions",
        type=int,
        default=int(os.getenv("EMBEDDING_DIM", str(DEFAULT_DIMENSIONS))),
    )
    args = parser.parse_args()

    embedder = MyEmbedder(args.model, args.dimensions)
    vector = embedder.embed_query("What is justice?")
    print(f"provider={embedder.provider}")
    print(f"model={embedder.model_name}")
    print(f"dimensions={len(vector)}")
    print(f"norm={math.sqrt(sum(value * value for value in vector)):.6f}")


if __name__ == "__main__":
    main()
