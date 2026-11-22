"""backend/embeddings.py - Local ONNX dense embedding generation.

Generates dense vector embeddings using local ONNX models via fastembed.
No external network calls, no rate limits, completely offline and deterministic.
"""

from __future__ import annotations

import math
import struct
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastembed import TextEmbedding

_EMBED_MODEL: TextEmbedding | None = None
MODEL_NAME = "BAAI/bge-small-en-v1.5"


def get_embedding_model() -> TextEmbedding:
    """Return the cached singleton fastembed TextEmbedding model."""
    global _EMBED_MODEL
    if _EMBED_MODEL is None:
        from fastembed import TextEmbedding

        _EMBED_MODEL = TextEmbedding(model_name=MODEL_NAME)
    return _EMBED_MODEL


def embed_text(text: str) -> list[float]:
    """Generate a 384-dimensional dense vector for a single string."""
    model = get_embedding_model()
    embeddings = list(model.embed([text]))
    return [float(v) for v in embeddings[0]]


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Generate dense vectors for a batch of strings."""
    if not texts:
        return []
    model = get_embedding_model()
    embeddings = list(model.embed(texts))
    return [[float(v) for v in vec] for vec in embeddings]


def serialize_vector(vector: list[float]) -> bytes:
    """Pack float vector into compact binary format for SQLite BLOB storage."""
    return struct.pack(f"{len(vector)}f", *vector)


def deserialize_vector(blob: bytes) -> list[float]:
    """Unpack binary SQLite BLOB back into float vector."""
    count = len(blob) // 4
    return list(struct.unpack(f"{count}f", blob))


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Compute standard cosine similarity between two float vectors."""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    dot = sum(a * b for a, b in zip(vec1, vec2, strict=False))
    norm_a = math.sqrt(sum(a * a for a in vec1))
    norm_b = math.sqrt(sum(b * b for b in vec2))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
