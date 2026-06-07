"""
Document loader backed by langchain-docling.

``langchain-docling`` wraps IBM Docling's DocumentConverter and exposes it
as a standard LangChain loader.  It handles layout-aware parsing, table
recovery, OCR, and structural chunking in one call.

Supported formats (handled by Docling internally):
  PDF, DOCX, PPTX, XLSX, XLS, HTML, TXT, CSV, Markdown, AsciiDoc, LaTeX,
  images (PNG/JPEG/TIFF/BMP/WEBP), EML, MSG …

Usage
-----
  # Load as pre-chunked LangChain Documents (recommended for RAG)
  docs = load_documents(file_path)          # list[Document]

  # Load as a single Markdown string (for storage / preview)
  md = load_as_markdown(file_path)          # str
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class ConversionError(RuntimeError):
    """Raised when Docling fails to convert a supported document."""


class UnsupportedFormatError(ValueError):
    """Raised when the file type cannot be processed."""


def load_documents(file_path: str) -> list["Document"]:
    """Parse *file_path* and return a list of layout-aware LangChain Documents.

    Uses ``ExportType.DOC_CHUNKS`` so each returned Document represents one
    coherent semantic chunk (section, paragraph, table, caption…) as
    determined by Docling's layout analysis.  Table rows are never split from
    their header; each table chunk is self-describing.

    Args:
        file_path: Absolute path to the document on disk.

    Returns:
        List of ``langchain_core.documents.Document`` objects.  Each has:
        - ``page_content``: the chunk text (Markdown)
        - ``metadata``:     dict with ``source``, ``dl_meta`` (Docling metadata)

    Raises:
        ConversionError:        Docling failed to parse the document.
        UnsupportedFormatError: The file type is not supported.
        FileNotFoundError:      ``file_path`` does not exist on disk.
    """
    try:
        from langchain_docling import DoclingLoader
        from langchain_docling.loader import ExportType
    except ImportError as exc:
        raise ConversionError(
            "langchain-docling is not installed. "
            "Add 'langchain-docling' to your dependencies."
        ) from exc

    try:
        loader = DoclingLoader(
            file_path=file_path,
            export_type=ExportType.DOC_CHUNKS,
        )
        docs = loader.load()
        logger.info(
            "DoclingLoader produced %d chunk(s) from '%s'", len(docs), file_path
        )
        return docs
    except Exception as exc:
        logger.error("DoclingLoader failed for '%s': %s", file_path, exc)
        raise ConversionError(
            f"Docling failed to parse '{file_path}': {exc}"
        ) from exc


def load_as_markdown(file_path: str) -> str:
    """Parse *file_path* and return the full document as a Markdown string.

    Useful for storing the raw parsed content in MySQL (``ParentDocument.content``).

    Args:
        file_path: Absolute path to the document on disk.

    Returns:
        Full Markdown string representation of the document.

    Raises:
        ConversionError: Docling failed to parse the document.
    """
    try:
        from langchain_docling import DoclingLoader
        from langchain_docling.loader import ExportType
    except ImportError as exc:
        raise ConversionError(
            "langchain-docling is not installed. "
            "Add 'langchain-docling' to your dependencies."
        ) from exc

    try:
        loader = DoclingLoader(
            file_path=file_path,
            export_type=ExportType.MARKDOWN,
        )
        docs = loader.load()
        # MARKDOWN export returns a single Document; join in case of multi-page.
        markdown = "\n\n".join(d.page_content for d in docs)
        logger.info(
            "DoclingLoader (MARKDOWN) produced %d chars from '%s'",
            len(markdown),
            file_path,
        )
        return markdown
    except Exception as exc:
        logger.error("DoclingLoader (MARKDOWN) failed for '%s': %s", file_path, exc)
        raise ConversionError(
            f"Docling failed to parse '{file_path}' as Markdown: {exc}"
        ) from exc
