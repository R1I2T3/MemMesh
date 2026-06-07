"""
Celery ingestion task: document hex → parse → MySQL → Weaviate.

The task is idempotent-friendly: if the MySQL commit fails the Weaviate
insert is never attempted, and the temp file is always cleaned up.
"""

from __future__ import annotations

import logging
import os
import tempfile
import uuid
from pathlib import Path

from backend.db.mysql import SessionLocal
from backend.db.weaviate import get_weaviate_mgr
from backend.ingestion.chunker import split_text_recursively
from backend.ingestion.parser import ConversionError, UnsupportedFormatError, parse_file_to_markdown
from backend.models import ParentDocument
from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def process_document_task(
    self,
    hex_content: str,
    filename: str,
    team_id: str,
    user_id: str,
) -> str:
    """Parse a document and index its chunks into MySQL + Weaviate.

    Args:
        hex_content:  Hex-encoded bytes of the uploaded file.
        filename:     Original filename (used for extension detection).
        team_id:      The team's UUID (also used as the Weaviate tenant shard).
        user_id:      Uploader's user UUID (added to ``allowed_user_ids``).

    Returns:
        The ``parent_id`` UUID string of the newly created ``ParentDocument``.

    Raises:
        UnsupportedFormatError: The file extension has no supported parser.
        ConversionError:        Docling failed to parse the document.
        Exception:              Any other unexpected error (triggers Celery retry).
    """
    # Preserve the original extension so Docling can detect the format.
    suffix = Path(filename).suffix or ".bin"
    file_bytes = bytes.fromhex(hex_content)

    # write to a named temp file; delete=False so the parser can open it by path
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_path = temp_file.name
    try:
        temp_file.write(file_bytes)
        temp_file.close()

        # ----------------------------------------------------------------
        # 1. Parse document → Markdown
        # ----------------------------------------------------------------
        try:
            markdown_content = parse_file_to_markdown(temp_path, filename=filename)
        except (UnsupportedFormatError, ConversionError):
            # These are user errors; do not retry.
            raise
        except Exception as exc:
            logger.warning("Transient parse error for %s; scheduling retry: %s", filename, exc)
            raise self.retry(exc=exc)

        # ----------------------------------------------------------------
        # 2. Persist ParentDocument in MySQL
        # ----------------------------------------------------------------
        parent_id = str(uuid.uuid4())
        db = SessionLocal()
        try:
            parent_doc = ParentDocument(
                parent_id=parent_id,
                filename=filename,
                content=markdown_content,
                team_id=team_id,
            )
            db.add(parent_doc)
            db.commit()
            logger.info("Saved ParentDocument %s for team %s", parent_id, team_id)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

        # ----------------------------------------------------------------
        # 3. Chunk and index into Weaviate
        # ----------------------------------------------------------------
        chunks = split_text_recursively(markdown_content, max_size=512, overlap=64)
        logger.info("Split %s into %d chunk(s)", filename, len(chunks))

        if chunks:
            weaviate_chunks = [
                {
                    "text": chunk_text,
                    "parent_id": parent_id,
                    "page_number": 1,   # Docling page info available via result.pages in v2
                    "bbox": [],
                }
                for chunk_text in chunks
            ]
            weaviate_mgr = get_weaviate_mgr()
            weaviate_mgr.insert_chunks(
                tenant_id=team_id,
                chunks=weaviate_chunks,
                allowed_users=[user_id, "public"],
            )
            logger.info("Indexed %d chunk(s) into Weaviate tenant %s", len(chunks), team_id)

        return parent_id

    finally:
        # Always remove the temp file, even on failure.
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError as exc:
                logger.warning("Failed to remove temp file %s: %s", temp_path, exc)
