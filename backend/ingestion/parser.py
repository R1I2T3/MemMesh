"""Multi-format document parser backed by Docling.

Supports: TXT, MD, HTML, PDF, DOCX, PPTX, XLSX, and images (via OCR).
Returns extracted, cleaned text from any supported document format.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ParseResult:
    """Result of parsing a single document."""

    text: str
    format: str
    page_count: int = 1
    headings: list[str] = field(default_factory=list)


# Formats natively handled by Docling's DocumentConverter
_DOCLING_FORMATS = {
    "pdf", "docx", "pptx", "xlsx",
    "html", "htm",
    "png", "jpg", "jpeg", "tiff", "bmp", "gif", "webp",
}

# Plain-text formats we handle ourselves (Docling adds no value here)
_PLAINTEXT_FORMATS = {"txt", "md"}


def _clean_text(text: str) -> str:
    """Clean extracted text: deduplicate whitespace, strip edges."""
    # Normalize Windows-style line endings to Unix-style
    text = text.replace("\r\n", "\n")
    # Strip trailing whitespace of each line
    text = re.sub(r"[^\S\r\n]+$", "", text, flags=re.MULTILINE)
    # Collapse multiple horizontal spaces inside lines to a single space
    text = re.sub(r"(?<=\S)[^\S\r\n]+", " ", text)
    # Collapse 3+ newlines into 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _parse_txt(path: Path) -> ParseResult:
    text = path.read_text(encoding="utf-8", errors="replace")
    return ParseResult(text=_clean_text(text), format="txt")


def _parse_md(path: Path) -> ParseResult:
    text = path.read_text(encoding="utf-8", errors="replace")
    # Remove code blocks before extracting headings to avoid matching code comments
    text_no_code = re.sub(r"```[\s\S]*?```", "", text)
    headings = re.findall(r"^#+\s+(.+)$", text_no_code, re.MULTILINE)
    # Strip any trailing hashes (e.g. ## Heading ##), preserving C#
    headings = [re.sub(r"\s+#+$", "", h).strip() for h in headings]
    return ParseResult(text=_clean_text(text), format="md", headings=headings)


def _parse_with_docling(path: Path) -> ParseResult:
    """Use Docling's DocumentConverter to parse the file."""
    from docling.document_converter import DocumentConverter
    from docling.datamodel.base_models import InputFormat
    from docling.document_converter import (
        PdfFormatOption,
        WordFormatOption,
        SimplePipeline,
    )

    converter = DocumentConverter()
    result = converter.convert(str(path))
    doc = result.document

    # Export to plain markdown — preserves structure and is clean text
    markdown = doc.export_to_markdown()
    text = _clean_text(markdown)

    # Extract headings: docling marks section headers in the document model
    headings: list[str] = []
    try:
        from docling_core.types.doc import SectionHeaderItem
        for item, _ in doc.iterate_items():
            if isinstance(item, SectionHeaderItem):
                headings.append(item.text)
    except Exception:
        # Fallback: parse headings from the exported markdown
        headings = re.findall(r"^#+\s+(.+)$", markdown, re.MULTILINE)
        headings = [re.sub(r"\s+#+$", "", h).strip() for h in headings]

    # Page count: inspect doc.pages if available
    page_count = 1
    try:
        if doc.pages:
            page_count = len(doc.pages)
    except Exception:
        pass

    ext = path.suffix.lstrip(".").lower()
    # Normalise htm -> html for consistency
    fmt = "html" if ext == "htm" else ext
    return ParseResult(
        text=text,
        format=fmt,
        page_count=page_count,
        headings=headings,
    )


def parse_document(path: str) -> ParseResult:
    """Parse a document file and return extracted text.

    Args:
        path: Absolute or relative path to the document file.

    Returns:
        ParseResult with cleaned text, format, page count, and headings.

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
