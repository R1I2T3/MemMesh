"""Multi-format document parser.

Supports: TXT, MD, HTML, PDF, DOCX, and images (via OCR).
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


# Mapping of file extensions to parser functions
_PARSERS: dict[str, callable] = {}


def _register(ext: str):
    """Decorator to register a parser function for a file extension."""
    def decorator(fn):
        _PARSERS[ext] = fn
        return fn
    return decorator


def _clean_text(text: str) -> str:
    """Clean extracted text: deduplicate whitespace, strip edges."""
    # Normalize Windows-style line endings to Unix-style
    text = text.replace("\r\n", "\n")
    # Strip trailing whitespace of each line, preserving leading spaces for indentation/layout
    text = re.sub(r"[^\S\r\n]+$", "", text, flags=re.MULTILINE)
    # Collapse multiple horizontal spaces inside lines to a single space, preserving leading indentation
    text = re.sub(r"(?<=\S)[^\S\r\n]+", " ", text)
    # Collapse 3+ newlines into 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip leading/trailing whitespace of entire string
    return text.strip()


@_register("txt")
def _parse_txt(path: str) -> ParseResult:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return ParseResult(text=_clean_text(text), format="txt")


@_register("md")
def _parse_md(path: str) -> ParseResult:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    # Remove code blocks before extracting headings to avoid matching code comments
    text_no_code = re.sub(r"```[\s\S]*?```", "", text)
    headings = re.findall(r"^#+\s+(.+)$", text_no_code, re.MULTILINE)
    # Strip any trailing hashes (e.g. ## Heading ##), preserving C#
    headings = [re.sub(r"\s+#+$", "", h).strip() for h in headings]
    return ParseResult(text=_clean_text(text), format="md", headings=headings)


@_register("html")
@_register("htm")
def _parse_html(path: str) -> ParseResult:
    import html2text

    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    converter = html2text.HTML2Text()
    converter.ignore_links = True
    converter.ignore_images = True
    converter.ignore_emphasis = True
    converter.body_width = 0  # No wrapping
    text = converter.handle(raw)
    
    # Extract headings from the converted markdown
    headings = re.findall(r"^#+\s+(.+)$", text, re.MULTILINE)
    # Strip any trailing hashes (e.g. ## Heading ##), preserving C#
    headings = [re.sub(r"\s+#+$", "", h).strip() for h in headings]
    
    return ParseResult(text=_clean_text(text), format="html", headings=headings)


@_register("pdf")
def _parse_pdf(path: str) -> ParseResult:
    import fitz  # PyMuPDF

    pages_text = []
    headings = []
    with fitz.open(path) as doc:
        try:
            toc = doc.get_toc()
            # TOC format: [level, title, page]
            headings = [item[1] for item in toc if len(item) > 1]
        except Exception:
            pass

        for page in doc:
            text = page.get_text("text")
            pages_text.append(text)

    full_text = "\n\n".join(pages_text)
    return ParseResult(
        text=_clean_text(full_text),
        format="pdf",
        page_count=len(pages_text),
        headings=headings,
    )


def _iter_block_items(parent):
    """Yield each paragraph and table child within *parent*, in document order."""
    from docx.document import Document as _Document
    from docx.table import _Cell, Table
    from docx.text.paragraph import Paragraph
    from docx.oxml.text.paragraph import CT_P
    from docx.oxml.table import CT_Tbl

    if isinstance(parent, _Document):
        parent_elm = parent.element.body
    elif isinstance(parent, _Cell):
        parent_elm = parent._tc
    else:
        raise ValueError("Parent must be a Document or _Cell")

    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)


@_register("docx")
def _parse_docx(path: str) -> ParseResult:
    from docx import Document
    from docx.text.paragraph import Paragraph
    from docx.table import Table

    doc = Document(path)
    paragraphs = []
    headings = []

    # Iterate through paragraphs and tables in natural XML document order
    for block in _iter_block_items(doc):
        if isinstance(block, Paragraph):
            if block.style and block.style.name and block.style.name.startswith("Heading"):
                headings.append(block.text)
            paragraphs.append(block.text)
        elif isinstance(block, Table):
            for row in block.rows:
                # Keep empty cells to maintain column structure alignment
                row_text = [cell.text.strip() for cell in row.cells]
                if any(row_text):
                    paragraphs.append(" | ".join(row_text))

    full_text = "\n".join(paragraphs)
    return ParseResult(
        text=_clean_text(full_text),
        format="docx",
        headings=headings,
    )


# Image formats — OCR via pytesseract
def _parse_image(path: str) -> ParseResult:
    from PIL import Image
    import pytesseract

    with Image.open(path) as img:
        text = pytesseract.image_to_string(img)
    ext = Path(path).suffix.lstrip(".").lower()
    return ParseResult(text=_clean_text(text), format=ext)


for _ext in ("png", "jpg", "jpeg", "tiff"):
    _PARSERS[_ext] = _parse_image


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
    parser = _PARSERS.get(ext)
    if parser is None:
        raise ValueError(
            f"Unsupported file format: .{ext}. "
            f"Supported formats: {', '.join(sorted(_PARSERS.keys()))}"
        )

    return parser(str(file_path))
