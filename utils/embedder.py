import os
from typing import List, Dict, Any
from google import genai
from dotenv import load_dotenv

load_dotenv()

MODEL = "text-embedding-004"

_client: genai.Client | None = None


def get_embedder_client() -> genai.Client:
    """Get or create the shared Google GenAI embedder client."""
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    return _client


def embed_chunks_with_client(
    chunks: List[Dict[str, Any]], client: genai.Client | None = None
) -> List[Dict[str, Any]]:
    """Embed chunks using the provided client, or fall back to the shared client."""
    if not chunks:
        return []

    client = client or get_embedder_client()

    try:
        texts = [chunk["text"] for chunk in chunks]
        response = client.models.embed_content(
            model=MODEL,
            contents=texts,
        )
        for i, chunk in enumerate(chunks):
            chunk["embedding"] = response.embeddings[i].values

    except Exception as e:
        raise RuntimeError(f"Embedding failed: {e}") from e

    return chunks


def embed_chunks(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Backward-compatible wrapper that uses the shared client."""
    return embed_chunks_with_client(chunks)
