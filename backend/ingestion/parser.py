"""
Document-to-Markdown parser backed by IBM Docling.

Docling natively supports:
  PDF, DOCX, PPTX, XLSX, HTML, Markdown, AsciiDoc, LaTeX,
  CSV, TXT, images (PNG/JPEG/TIFF/BMP/WEBP), EML, MSG …

Formats NOT supported by Docling (handled with fallbacks):
  .doc / .odt / .rtf / .key / .gsheet / .gslides
      → converted to text via python-docx / odfpy / striprtf / plaintext read
  .zip / .7z / .rar (archive containers)
      → rejected with a clear UnsupportedFormatError so the caller can decide
  .json / .xml
      → read as plain text (already structured, no layout analysis needed)
"""

from __future__ import annotations

import json
import logging
import os
import zipfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Docling format mapping
# ---------------------------------------------------------------------------

# Extensions natively handled by Docling's DocumentConverter
_DOCLING_EXTENSIONS: set[str] = {
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".html",
    ".htm",
    ".xhtml",
    ".md",
    ".markdown",
    ".adoc",
    ".asciidoc",
    ".tex",
    ".csv",
    ".txt",
    ".png",
    ".jpg",
    ".jpeg",
    ".tiff",
    ".tif",
    ".bmp",
    ".webp",
    ".eml",
    ".msg",
}

# Extensions that need a pre-processing fallback before being sent to Docling
# (or that we convert to plain-text directly)
_PLAINTEXT_EXTENSIONS: set[str] = {".json", ".xml"}
_ARCHIVE_EXTENSIONS: set[str] = {".zip", ".7z", ".rar"}


class UnsupportedFormatError(ValueError):
    """Raised when the file extension is not supported and has no fallback."""


class ConversionError(RuntimeError):
    """Raised when Docling fails to convert a supported document."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _read_as_plain_text(file_path: str) -> str:
    """Read any text-like file and return its raw content as a string."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _fallback_docx_to_text(file_path: str) -> str:
    """Extract text from legacy .doc / .odt using python-docx or raw read."""
    try:
        from docx import Document  # python-docx

        doc = Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)
    except Exception:
        # Last resort: read bytes as UTF-8 (will be garbled but better than nothing)
        return _read_as_plain_text(file_path)


def _fallback_rtf_to_text(file_path: str) -> str:
    """Strip RTF markup and return plain text."""
    try:
        from striprtf.striprtf import rtf_to_text  # type: ignore[import]

        raw = Path(file_path).read_bytes().decode("utf-8", errors="replace")
        return rtf_to_text(raw)
    except Exception:
        return _read_as_plain_text(file_path)


def _fallback_odf_to_text(file_path: str) -> str:
    """Extract text from ODF documents (odt, ods, odp, key) using odfpy."""
    try:
        from odf import text as odf_text  # type: ignore[import]
        from odf.opendocument import load as odf_load  # type: ignore[import]
        from odf.teletype import extractText  # type: ignore[import]

        doc = odf_load(file_path)
        parts = doc.getElementsByType(odf_text.P)
        return "\n".join(extractText(p) for p in parts if extractText(p).strip())
    except Exception:
        return _read_as_plain_text(file_path)


def _fallback_zip_contents(file_path: str) -> str:
    """Extract readable text files from a ZIP archive and concatenate them."""
    if not zipfile.is_zipfile(file_path):
        raise UnsupportedFormatError(f"Not a valid ZIP file: {file_path}")

    text_parts: list[str] = []
    with zipfile.ZipFile(file_path, "r") as zf:
        for name in zf.namelist():
            ext = Path(name).suffix.lower()
            if ext in (".txt", ".md", ".csv", ".json", ".xml", ".html", ".htm"):
                try:
                    with zf.open(name) as entry:
                        content = entry.read().decode("utf-8", errors="replace")
                        text_parts.append(f"--- {name} ---\n{content}")
                except Exception as exc:
                    logger.warning("Skipping %s inside archive: %s", name, exc)

    if not text_parts:
        raise UnsupportedFormatError(
            f"ZIP archive at {file_path} contained no extractable text files."
        )
    return "\n\n".join(text_parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_file_to_markdown(file_path: str, filename: Optional[str] = None) -> str:
    """Convert a document at *file_path* to Markdown text.

    The function first checks the file extension to decide which processing
    path to take:

    * **Docling-native** (PDF, DOCX, PPTX, XLSX, HTML, TXT, CSV, images …):
      passed directly to ``DocumentConverter``.  Layout analysis, table
      recovery, and OCR are handled automatically by Docling.
    * **Plain-text structured** (JSON, XML):
      read directly as UTF-8 text and returned as a fenced code block.
    * **Legacy / alternative formats** (.doc, .odt, .rtf, .key, .gsheet …):
      converted to plain text with format-specific fallback libraries.
    * **Archives** (.zip, .7z, .rar):
      ZIP archives are unpacked and text-like members are concatenated.
      .7z and .rar require additional tools and raise ``UnsupportedFormatError``.

    Args:
        file_path:  Absolute or relative path to the document on disk.
        filename:   Original filename (used for extension detection when the
                    temp-file path has a generic suffix).  Defaults to
                    ``file_path`` basename.

    Returns:
        Markdown string representation of the document content.

    Raises:
        UnsupportedFormatError:  Extension has no supported conversion path.
        ConversionError:         Docling failed to parse a supported document.
        FileNotFoundError:       ``file_path`` does not exist.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Document not found: {file_path}")

    # Prefer the original filename for extension detection (temp files may lack it)
    name_for_ext = filename or os.path.basename(file_path)
    ext = Path(name_for_ext).suffix.lower()

    logger.info("Parsing document: %s (ext=%s)", name_for_ext, ext)

    # ------------------------------------------------------------------
    # 1. Plain-text structured formats (JSON, XML)
    # ------------------------------------------------------------------
    if ext in _PLAINTEXT_EXTENSIONS:
        raw = _read_as_plain_text(file_path)
        lang = "json" if ext == ".json" else "xml"
        return f"```{lang}\n{raw}\n```"

    # ------------------------------------------------------------------
    # 2. Archive formats
    # ------------------------------------------------------------------
    if ext in _ARCHIVE_EXTENSIONS:
        if ext == ".zip":
            return _fallback_zip_contents(file_path)
        raise UnsupportedFormatError(
            f"Archive format '{ext}' is not supported.  "
            "Please extract the contents and upload individual files."
        )

    # ------------------------------------------------------------------
    # 3. Legacy / alternative formats without Docling support
    # ------------------------------------------------------------------
    if ext in (".doc",):
        text = _fallback_docx_to_text(file_path)
        return text

    if ext in (".rtf",):
        text = _fallback_rtf_to_text(file_path)
        return text

    if ext in (".odt", ".ods", ".odp", ".key"):
        text = _fallback_odf_to_text(file_path)
        return text

    if ext in (".gsheet", ".gslides", ".gdoc"):
        raise UnsupportedFormatError(
            f"Google Workspace format '{ext}' cannot be ingested directly.  "
            "Please export to PDF, XLSX, PPTX, or CSV and re-upload."
        )

    # ------------------------------------------------------------------
    # 4. Docling-native formats (PDF, DOCX, PPTX, XLSX, HTML, CSV, …)
    # ------------------------------------------------------------------
    if ext in _DOCLING_EXTENSIONS or ext == "":
        return _convert_with_docling(file_path)

    # ------------------------------------------------------------------
    # 5. Unknown extension – attempt Docling anyway, fail gracefully
    # ------------------------------------------------------------------
    logger.warning(
        "Unknown extension '%s' for file %s; attempting Docling conversion.",
        ext,
        name_for_ext,
    )
    try:
        return _convert_with_docling(file_path)
    except Exception as exc:
        raise UnsupportedFormatError(
            f"No supported conversion path for extension '{ext}': {exc}"
        ) from exc


def _convert_with_docling(file_path: str) -> str:
    """Run Docling's DocumentConverter and return Markdown output."""
    try:
        from docling.document_converter import DocumentConverter  # noqa: WPS433

        converter = DocumentConverter()
        result = converter.convert(file_path)
        markdown = result.document.export_to_markdown()
        logger.info("Docling conversion successful for %s (%d chars)", file_path, len(markdown))
        return markdown
    except Exception as exc:
        logger.error("Docling conversion failed for %s: %s", file_path, exc)
        raise ConversionError(f"Docling failed to parse '{file_path}': {exc}") from exc
