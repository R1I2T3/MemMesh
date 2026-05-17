import os
from typing import List, Dict, Any
from google import genai
from dotenv import load_dotenv

load_dotenv()

MODEL = "text-embedding-004"

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """Get or create the singleton Google GenAI client."""
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    return _client


def embed_chunks(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not chunks:
        return []

    client = _get_client()

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
