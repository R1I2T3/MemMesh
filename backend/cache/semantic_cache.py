import json
import hashlib
import struct
import logging
from typing import Any, Dict, Optional
from backend.agents.memory import get_redis_client
from backend.config import settings
from backend.db.weaviate import GoogleGenerativeAIEmbeddings

logger = logging.getLogger(__name__)

_cache_instance = None


def get_cache() -> "SemanticCache":
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = SemanticCache()
    return _cache_instance


class SemanticCache:
    def __init__(self):
        self.redis = get_redis_client()
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-2",
            google_api_key=settings.GEMINI_API_KEY
        )
        self.threshold = settings.SEMANTIC_CACHE_THRESHOLD
        self.ttl = settings.SEMANTIC_CACHE_TTL

    def _embed(self, text: str) -> list[float]:
        return self.embeddings.embed_query(text)

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        dot = sum(x*y for x, y in zip(a, b))
        norm_a = sum(x*x for x in a)**0.5
        norm_b = sum(x*x for x in b)**0.5
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

    def _hash_key(self, embedding: list[float]) -> str:
        key_bytes = struct.pack('f'*min(4, len(embedding)), *embedding[:4])
        return hashlib.md5(key_bytes).hexdigest()

    def get(self, query: str) -> Optional[Dict[str, Any]]:
        query_emb = self._embed(query)
        cache_key = f"semantic_cache:{self._hash_key(query_emb)}"
        cached = self.redis.get(cache_key)
        if cached:
            entry = json.loads(cached)
            stored_emb = entry.get("embedding", [])
            similarity = self._cosine_similarity(query_emb, stored_emb)
            if similarity >= self.threshold:
                logger.info(f"Semantic cache HIT (similarity: {similarity:.3f})")
                return entry.get("result")
        logger.debug("Semantic cache MISS")
        return None

    def set(self, query: str, result: Dict[str, Any]):
        query_emb = self._embed(query)
        cache_key = f"semantic_cache:{self._hash_key(query_emb)}"
        entry = {"embedding": query_emb, "result": result}
        self.redis.set(cache_key, json.dumps(entry), ex=self.ttl)

    def flush(self):
        keys = self.redis.keys("semantic_cache:*")
        if keys:
            self.redis.delete(*keys)
            logger.info(f"Flushed {len(keys)} semantic cache entries")
