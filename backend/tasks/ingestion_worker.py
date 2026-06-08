"""
Celery ingestion task: document hex → DoclingLoader → MySQL → Weaviate.

Parsing and chunking are both delegated to ``langchain-docling``'s
``DoclingLoader`` with ``ExportType.DOC_CHUNKS``.  This produces layout-aware
chunks that respect document structure (sections, tables, captions) and never
split a Markdown table row from its header.

Single parse pass
-----------------
The document is loaded once with ``DOC_CHUNKS`` to get the semantic chunks.
The full Markdown stored in MySQL is assembled by joining chunk texts —
no second Docling parse needed.

Idempotency
-----------
``parent_id`` is derived deterministically from the SHA-256 hash of the raw
document bytes.  Retrying the same file always produces the same ID, and
the MySQL INSERT uses ``INSERT IGNORE`` so duplicate rows are silently skipped.

Error classification
--------------------
* ``ConversionError``:         Docling parsing failure — not retriable.
* ``UnsupportedFormatError``:  Unsupported file type — not retriable.
* Any other exception:         Treated as transient; retried up to 3 times
                               with a 30-second delay.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from pathlib import Path

from sqlalchemy.dialects.mysql import insert as mysql_insert

from backend.db.mysql import SessionLocal
from backend.db.weaviate import WeaviateManager
from backend.db.neo4j import Neo4jManager
from backend.ingestion.parser import ConversionError, UnsupportedFormatError, load_documents
from backend.ingestion.extractor import extract_entities_and_relationships
from backend.models import ParentDocument
from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _deterministic_id(data: bytes) -> str:
    """Stable UUID-shaped string derived from the SHA-256 of the file bytes.

    Ensures that retrying the same document always produces the same
    ``parent_id``, making MySQL and Weaviate writes idempotent.
    """
    digest = hashlib.sha256(data).hexdigest()
    return f"{digest[:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:32]}"


def _page_number_from_meta(meta: dict) -> int:
    """Extract page number from Docling's ``dl_meta`` chunk metadata.

    ``dl_meta`` structure (from langchain-docling)::

        {
          "doc_items": [{"prov": [{"page_no": 2, ...}], ...}],
          ...
        }

    Returns 1 as a safe default when the key is absent.
    """
    try:
        return int(
            meta.get("dl_meta", {})
            .get("doc_items", [{}])[0]
            .get("prov", [{}])[0]
            .get("page_no", 1)
        )
    except (IndexError, TypeError, ValueError):
        return 1


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def process_document_task(
    self,
    hex_content: str,
    filename: str,
    team_id: str,
    user_id: str,
) -> str:
    """Parse a document and index its chunks into MySQL + Weaviate.

    Pipeline::

        hex_content
            → bytes
            → temp file  (extension preserved for Docling format detection)
            → load_documents()  (DOC_CHUNKS: parse + layout-aware chunk)
            → MySQL ParentDocument  (full Markdown assembled from chunks)
            → Weaviate batch insert  (per-chunk, under team tenant shard)
            → temp file cleanup

    Args:
        hex_content:  Hex-encoded bytes of the uploaded file.
        filename:     Original filename (used for extension detection).
        team_id:      Team UUID — also the Weaviate tenant shard.
        user_id:      Uploader UUID — added to ``allowed_user_ids``.

    Returns:
        The ``parent_id`` UUID string of the ``ParentDocument`` record.

    Raises:
        ConversionError:        Docling failed to parse the document.
        UnsupportedFormatError: File type has no supported parser.
        Exception:              Any other error triggers Celery retry.
    """
    file_bytes = bytes.fromhex(hex_content)
    parent_id = _deterministic_id(file_bytes)

    # Preserve original file extension so Docling can detect the format.
    suffix = Path(filename).suffix or ".bin"
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_path = temp_file.name

    try:
        temp_file.write(file_bytes)
        temp_file.close()

        # ----------------------------------------------------------------
        # 1. Parse + chunk via langchain-docling (single parse pass)
        # ----------------------------------------------------------------
        try:
            docs = load_documents(temp_path)
        except (ConversionError, UnsupportedFormatError):
            # User-caused errors — do not retry.
            raise
        except Exception as exc:
            logger.warning(
                "Transient parse error for '%s'; scheduling retry: %s", filename, exc
            )
            raise self.retry(exc=exc)

        logger.info(
            "DoclingLoader produced %d chunk(s) for '%s'", len(docs), filename
        )

        # Assemble full Markdown from chunks for MySQL storage.
        # This avoids a second Docling parse pass (load_as_markdown is not called).
        # Note: joining chunks with "\n\n" is lossy — the reconstructed Markdown
        # may differ structurally from what load_as_markdown() would produce.
        # For a faithful copy, call load_as_markdown() in a second pass instead.
        markdown_content = "\n\n".join(doc.page_content for doc in docs)

        # ----------------------------------------------------------------
        # 2. Persist ParentDocument in MySQL (idempotent via INSERT IGNORE)
        # ----------------------------------------------------------------
        db = SessionLocal()
        try:
            stmt = (
                mysql_insert(ParentDocument)
                .values(
                    parent_id=parent_id,
                    filename=filename,
                    content=markdown_content,
                    team_id=team_id,
                )
                .prefix_with("IGNORE")  # silently skips duplicate PKs on retry
            )
            db.execute(stmt)
            db.commit()
            logger.info("Saved ParentDocument %s for team %s", parent_id, team_id)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

        # ----------------------------------------------------------------
        # 3. Batch-insert chunks into Weaviate
        # ----------------------------------------------------------------
        if docs:
            weaviate_chunks = [
                {
                    "text": doc.page_content,
                    "parent_id": parent_id,
                    "page_number": _page_number_from_meta(doc.metadata or {}),
                    "bbox": [],
                    # Store raw dl_meta as JSON string for downstream spatial /
                    # citation queries.  Parse with json.loads() on retrieval.
                    "dl_meta": json.dumps((doc.metadata or {}).get("dl_meta", {})),
                }
                for doc in docs
            ]

            # Instantiate WeaviateManager fresh per task — avoids fork-unsafe
            # gRPC connection reuse across Celery worker processes.
            weaviate_mgr = WeaviateManager()
            try:
                weaviate_mgr.insert_chunks(
                    tenant_id=team_id,
                    chunks=weaviate_chunks,
                    allowed_users=[user_id, "public"],
                )
                logger.info(
                    "Indexed %d chunk(s) into Weaviate tenant '%s'",
                    len(weaviate_chunks),
                    team_id,
                )
            finally:
                weaviate_mgr.close()

            # ----------------------------------------------------------------
            # 4. Extract entities and relationships and write to Neo4j
            # ----------------------------------------------------------------
            neo4j_mgr = Neo4jManager()
            try:
                for doc in docs:
                    entities, relationships = extract_entities_and_relationships(doc.page_content)
                    # Write entities
                    for entity in entities:
                        if not isinstance(entity, dict):
                            logger.warning("Extracted entity is not a dictionary: %s", entity)
                            continue
                        ent_id = entity.get("id")
                        name = entity.get("name")
                        if not ent_id or not name:
                            logger.warning("Skipping invalid entity (missing id/name): %s", entity)
                            continue
                        neo4j_mgr.write_entity(
                            team_id=team_id,
                            entity_id=ent_id,
                            name=name,
                            entity_type=entity.get("type", "Concept") or "Concept",
                            source_doc_id=parent_id
                        )
                    # Write relationships
                    for rel in relationships:
                        if not isinstance(rel, dict):
                            logger.warning("Extracted relationship is not a dictionary: %s", rel)
                            continue
                        source_id = rel.get("source_id")
                        target_id = rel.get("target_id")
                        if not source_id or not target_id:
                            logger.warning("Skipping invalid relationship (missing source/target): %s", rel)
                            continue
                        neo4j_mgr.write_relationship(
                            team_id=team_id,
                            source_id=source_id,
                            target_id=target_id,
                            rel_type=rel.get("type", "RELATES_TO") or "RELATES_TO"
                        )
                logger.info(
                    "Extracted and saved knowledge graph entities/relationships to Neo4j for team '%s'",
                    team_id,
                )
            except Exception as neo4j_exc:
                logger.error("Failed writing entities to Neo4j: %s", neo4j_exc)
                raise
            finally:
                neo4j_mgr.close()

        return parent_id

    finally:
        # Always clean up the temp file, even on failure or retry.
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError as exc:
                logger.warning("Failed to remove temp file %s: %s", temp_path, exc)
