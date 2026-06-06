"""Multi-format document parser backed by Docling.

Supports: TXT, MD, HTML, PDF, DOCX, PPTX, XLSX, and images (via OCR).
Returns extracted, cleaned text and a DoclingDocument from any supported format.

Note: page_count defaults to 1 for formats without real page metadata (txt, md).
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ParseResult:
    """Result of parsing a single document."""

    text: str
    format: str
    page_count: int = 1
    headings: list[str] = field(default_factory=list)
    # DoclingDocument object — present for all formats, enables HybridChunker
    doc: Any | None = None


# Formats natively handled by Docling's DocumentConverter
_DOCLING_FORMATS = {
    "pdf", "docx", "pptx", "xlsx",
    "html", "htm",
    "png", "jpg", "jpeg", "tiff", "bmp", "gif", "webp",
}

# Plain-text formats we convert via convert_string so HybridChunker can be used
_PLAINTEXT_FORMATS = {"txt", "md"}

# Module-level singleton — DocumentConverter loads ML pipelines at construction;
# re-instantiating on every call is expensive. Lazily initialised on first use.
_converter = None


def _get_converter() -> Any:
    """Return the cached DocumentConverter, creating it on first call."""
    global _converter
    if _converter is None:
        from docling.document_converter import DocumentConverter
        _converter = DocumentConverter()
        logger.debug("DocumentConverter initialised")
    return _converter


def _clean_text(text: str) -> str:
    """Clean extracted text: deduplicate whitespace, strip edges."""
    text = text.replace("\r\n", "\n")
    text = re.sub(r"[^\S\r\n]+$", "", text, flags=re.MULTILINE)
    text = re.sub(r"(?<=\S)[^\S\r\n]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _headings_from_doc(doc: Any) -> list[str]:
    """Extract headings from a DoclingDocument.

    Docling maps H1 to TitleItem and H2+ to SectionHeaderItem.
    We collect both in document order so the full heading hierarchy is preserved.
    """
    headings: list[str] = []
    try:
        from docling_core.types.doc import SectionHeaderItem, TitleItem
        for item, _ in doc.iterate_items():
            if isinstance(item, (TitleItem, SectionHeaderItem)):
                headings.append(item.text)
    except Exception:
        logger.debug("Could not extract headings from DoclingDocument", exc_info=True)
    return headings


def _page_count_from_doc(doc: Any) -> int:
    """Extract page count from a DoclingDocument."""
    try:
        if doc.pages:
            return len(doc.pages)
    except Exception:
        logger.debug("Could not extract page count from DoclingDocument", exc_info=True)
    return 1


def _convert_string_to_doc(text: str, fmt: str) -> Any | None:
    """Convert a plain text/markdown string into a DoclingDocument via convert_string.

    Both txt and md are treated as Markdown (InputFormat.MD) since txt renders
    cleanly as plain paragraphs and md is natively Markdown.
    """
    try:
        from docling.datamodel.base_models import InputFormat
        converter = _get_converter()
        result = converter.convert_string(text, format=InputFormat.MD, name=f"document.{fmt}")
        return result.document
    except Exception:
        logger.warning(
            "convert_string failed for format '%s'; doc field will be None",
            fmt,
            exc_info=True,
        )
        return None


def _parse_txt(path: Path) -> ParseResult:
    text = path.read_text(encoding="utf-8", errors="replace")
    cleaned = _clean_text(text)
    doc = _convert_string_to_doc(cleaned, "txt")
    return ParseResult(text=cleaned, format="txt", doc=doc)


def _parse_md(path: Path) -> ParseResult:
    text = path.read_text(encoding="utf-8", errors="replace")
    cleaned = _clean_text(text)
    doc = _convert_string_to_doc(cleaned, "md")

    # Extract headings from markdown source (remove code blocks first)
    text_no_code = re.sub(r"```[\s\S]*?```", "", text)
    headings = re.findall(r"^#+\s+(.+)$", text_no_code, re.MULTILINE)
    headings = [re.sub(r"\s+#+$", "", h).strip() for h in headings]

    # Prefer doc-derived headings if available
    if doc:
        doc_headings = _headings_from_doc(doc)
        if doc_headings:
            headings = doc_headings

    return ParseResult(text=cleaned, format="md", headings=headings, doc=doc)


def _parse_with_docling(path: Path) -> ParseResult:
    """Use Docling's DocumentConverter to parse the file."""
    converter = _get_converter()
    result = converter.convert(str(path))
    doc = result.document

    markdown = doc.export_to_markdown()
    text = _clean_text(markdown)

    headings = _headings_from_doc(doc)
    if not headings:
        # Fallback: parse headings from the exported markdown
        headings = re.findall(r"^#+\s+(.+)$", markdown, re.MULTILINE)
        headings = [re.sub(r"\s+#+$", "", h).strip() for h in headings]

    page_count = _page_count_from_doc(doc)

    ext = path.suffix.lstrip(".").lower()
    fmt = "html" if ext == "htm" else ext
    return ParseResult(
        text=text,
        format=fmt,
        page_count=page_count,
        headings=headings,
        doc=doc,
    )


def parse_document(path: str) -> ParseResult:
    """Parse a document file and return extracted text and DoclingDocument.

    Args:
        path: Absolute or relative path to the document file.

    Returns:
        ParseResult with cleaned text, format, page count, headings,
        and a DoclingDocument (``doc``) for use with HybridChunker.
        ``page_count`` defaults to 1 for formats without real page metadata
        (txt, md).

    Raises:
        ValueError: If the file format is not supported or if the path is a directory.
        FileNotFoundError: If the file does not exist.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not file_path.is_file():
        raise ValueError(f"Path is not a file: {path}")

    ext = file_path.suffix.lstrip(".").lower()

    if ext == "txt":
        return _parse_txt(file_path)
    if ext == "md":
        return _parse_md(file_path)
    if ext in _DOCLING_FORMATS:
        return _parse_with_docling(file_path)

    supported = sorted(_PLAINTEXT_FORMATS | _DOCLING_FORMATS)
    raise ValueError(
        f"Unsupported file format: .{ext}. "
        f"Supported formats: {', '.join(supported)}"
    )
