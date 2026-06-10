import hashlib
import json
import math
from typing import Iterable


class EmbeddingProvider:
    def embed_text(self, text: str) -> list[float]:
        raise NotImplementedError


class HashEmbeddingProvider(EmbeddingProvider):
    """Small deterministic local embedding stub for MVP/demo use."""

    def __init__(self, dimensions: int = 64) -> None:
        self.dimensions = dimensions

    def embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in _tokens(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign
        return normalize(vector)


def get_embedding_provider() -> EmbeddingProvider:
    # TODO: Swap this for CLIP/keyframe embeddings or a hosted embedding provider.
    return HashEmbeddingProvider()


def _tokens(text: str) -> Iterable[str]:
    normalized = "".join(ch.lower() if ch.isalnum() else " " for ch in text)
    return (token for token in normalized.split() if token)


def normalize(vector: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0:
        return vector
    return [value / magnitude for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    return sum(a * b for a, b in zip(left, right))


def dumps_embedding(vector: list[float]) -> str:
    return json.dumps(vector, separators=(",", ":"))


def loads_embedding(raw: str | None) -> list[float]:
    if not raw:
        return []
    try:
        return [float(value) for value in json.loads(raw)]
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
