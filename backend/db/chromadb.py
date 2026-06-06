# backend/db/chromadb.py
"""ChromaDB wrapper with team-scoped collections.

Each team gets a dedicated collection named ``team_{team_id}``.

Embedding strategy:
  - In production (GEMINI_API_KEY set): uses ``GoogleGeminiEmbeddingFunction``
    with model ``settings.embedding_model`` (default ``text-embedding-004``).
  - Fallback / tests (no API key): uses ChromaDB's built-in
    ``DefaultEmbeddingFunction`` (ONNX MiniLM-L6-v2, ~384 dims, runs locally).
  - Tests can inject a custom ``EmbeddingFunction`` via the ``_EF_OVERRIDE``
    module-level variable to avoid API calls entirely.

The ChromaDB client is managed as a singleton so connections are reused
across calls within the same process.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from config import settings
from ingestion.chunker import Chunk

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Embedding function resolution
# ---------------------------------------------------------------------------

# Tests can set this to inject a mock / local EF without touching config.
_EF_OVERRIDE: Any | None = None


def _build_embedding_function() -> Any:
    """Return the appropriate ChromaDB EmbeddingFunction.

    Priority:
    1. ``_EF_OVERRIDE`` — allows test injection without env changes.
    2. ``GoogleGeminiEmbeddingFunction`` when ``GEMINI_API_KEY`` is set.
    3. ``DefaultEmbeddingFunction`` (ONNX MiniLM, runs locally, no API key).
    """
    from chromadb.utils import embedding_functions

    if _EF_OVERRIDE is not None:
        return _EF_OVERRIDE

    if settings.gemini_api_key:
        try:
            ef = embedding_functions.GoogleGeminiEmbeddingFunction(
                model_name=settings.embedding_model,
                api_key_env_var="GEMINI_API_KEY",
            )
            logger.debug("Using GoogleGeminiEmbeddingFunction (model=%s)", settings.embedding_model)
            return ef
        except Exception:
            logger.warning(
                "Could not initialise GoogleGeminiEmbeddingFunction; "
                "falling back to DefaultEmbeddingFunction.",
                exc_info=True,
            )

    logger.debug(
        "GEMINI_API_KEY not set — using DefaultEmbeddingFunction (ONNX MiniLM-L6-v2)."
    )
    return embedding_functions.DefaultEmbeddingFunction()


# ---------------------------------------------------------------------------
# Singleton client
# ---------------------------------------------------------------------------


class ChromaDBClient:
    """Singleton ChromaDB client manager."""

    _client: chromadb.ClientAPI | None = None

    @classmethod
    def get_client(cls) -> chromadb.ClientAPI:
        """Get or create the persistent ChromaDB client."""
        if cls._client is None:
            chroma_path = Path(settings.chroma_dir)
            chroma_path.mkdir(parents=True, exist_ok=True)
            cls._client = chromadb.PersistentClient(
                path=str(chroma_path),
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=True,
                ),
            )
        return cls._client

    @classmethod
    def reset(cls) -> None:
        """Reset the client — wipes all collections (for testing).

        Calls ``client.reset()`` to clear on-disk state, then discards the
        singleton so the next ``get_client()`` creates a fresh instance.
        """
        if cls._client is not None:
            try:
                cls._client.reset()
            except Exception:
                pass
            cls._client = None


# ---------------------------------------------------------------------------
# Collection helpers
# ---------------------------------------------------------------------------


def _collection_name(team_id: str) -> str:
    """Return the ChromaDB collection name for a team."""
    return f"team_{team_id}"


def get_or_create_collection(team_id: str) -> chromadb.Collection:
    """Get or create a ChromaDB collection for a team.

    Args:
        team_id: The team identifier.

    Returns:
        ChromaDB Collection instance.
    """
    client = ChromaDBClient.get_client()
    ef = _build_embedding_function()

    return client.get_or_create_collection(
        name=_collection_name(team_id),
        embedding_function=ef,
        metadata={"team_id": team_id},
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def upsert_chunks(team_id: str, chunks: list[Chunk]) -> None:
    """Upsert text chunks into a team's ChromaDB collection.

    Args:
        team_id: The team that owns these chunks.
        chunks: List of Chunk objects to upsert.
    """
    if not chunks:
        return

    collection = get_or_create_collection(team_id)

    ids = [c.chunk_id for c in chunks]
    documents = [c.text for c in chunks]
    metadatas = [
        {
            "team_id": c.team_id,
            "source_doc_id": c.source_doc_id,
            "index": c.index,
            "char_offset": c.char_offset,
            "page_number": c.page_number,
            "section_heading": c.section_heading or "",
        }
        for c in chunks
    ]

    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
    )


def query_collection(
    team_id: str,
    query_text: str,
    n_results: int = 10,
) -> list[dict[str, Any]]:
    """Query a team's ChromaDB collection by semantic similarity.

    Args:
        team_id: The team whose collection to query.
        query_text: The search query string.
        n_results: Maximum number of results to return.

    Returns:
        List of dicts with keys: chunk_id, text, score, team_id,
        source_doc_id, page_number, section_heading.
        Returns an empty list if the collection does not exist or is empty.
    """
    client = ChromaDBClient.get_client()
    col_name = _collection_name(team_id)

    # Check if collection exists — list_collections returns Collection objects
    existing_names = [c.name for c in client.list_collections()]
    if col_name not in existing_names:
        return []

    ef = _build_embedding_function()
    collection = client.get_collection(name=col_name, embedding_function=ef)

    # Guard against empty collections — ChromaDB raises if n_results > count
    count = collection.count()
    if count == 0:
        return []

    results = collection.query(
        query_texts=[query_text],
        n_results=min(n_results, count),
    )

    output: list[dict[str, Any]] = []
    if results and results["ids"] and results["ids"][0]:
        for i, chunk_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results["distances"] else 0.0
            doc_text = results["documents"][0][i] if results["documents"] else ""

            output.append(
                {
                    "chunk_id": chunk_id,
                    "text": doc_text,
                    # Convert L2 distance to approximate similarity (clamped to [0, 1])
                    "score": max(0.0, 1.0 - distance),
                    "team_id": meta.get("team_id", team_id),
                    "source_doc_id": meta.get("source_doc_id", ""),
                    "page_number": meta.get("page_number", 1),
                    "section_heading": meta.get("section_heading", ""),
                }
            )

    return output


def delete_collection(team_id: str) -> None:
    """Delete a team's ChromaDB collection.

    Safe to call if the collection doesn't exist.

    Args:
        team_id: The team whose collection to delete.
    """
    client = ChromaDBClient.get_client()
    col_name = _collection_name(team_id)

    try:
        client.delete_collection(name=col_name)
    except Exception:
        # Collection doesn't exist — that's fine
        pass
