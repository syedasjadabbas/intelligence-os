from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union
import pypdf


class PDFParsingError(Exception):
    """Custom exception raised when PDF parsing fails."""
    pass


@dataclass
class PageContent:
    """Structured representation of a parsed PDF page."""
    page_number: int  # 1-indexed
    text: str
    heading: Optional[str] = None


def detect_heading(line: str) -> Optional[str]:
    """
    Detect whether a text line qualifies as a section heading:
    - Markdown headings (# Heading, ## Subheading)
    - All-caps titles (e.g., 'EXECUTIVE SUMMARY', 'SECTION 1: OVERVIEW')
    - Short colon-terminated headers (e.g., 'Key Architecture Findings:')
    """
    cleaned = line.strip()
    if not cleaned:
        return None

    # Markdown syntax
    if cleaned.startswith("#"):
        heading_text = cleaned.lstrip("#").strip()
        return heading_text if heading_text else None

    words = cleaned.split()
    # Heading length heuristics: short line, not ending in period
    if 1 <= len(words) <= 12 and len(cleaned) <= 100:
        if cleaned.isupper() and any(c.isalpha() for c in cleaned):
            return cleaned.rstrip(":")
        if cleaned.endswith(":") and not cleaned.endswith(".."):
            return cleaned.rstrip(":")

    return None


def parse_pdf(file_path: Union[str, Path]) -> List[PageContent]:
    """
    Extracts text page by page from a PDF file.
    Preserves 1-indexed page numbers and section heading context.
    Raises PDFParsingError for encrypted, empty, or corrupted files.
    """
    path = Path(file_path)
    if not path.is_file():
        raise PDFParsingError(f"PDF file does not exist at path: {path}")

    try:
        reader = pypdf.PdfReader(str(path))
    except Exception as exc:
        raise PDFParsingError(f"Malformed or corrupted PDF file: {exc}")

    if reader.is_encrypted:
        try:
            # Check if empty password decrypts
            decrypt_res = reader.decrypt("")
            if decrypt_res == 0:
                raise PDFParsingError("PDF file is password protected and cannot be processed.")
        except Exception:
            raise PDFParsingError("PDF file is password protected or has unsupported encryption.")

    total_pages = len(reader.pages)
    if total_pages == 0:
        raise PDFParsingError("PDF file contains no pages.")

    parsed_pages: List[PageContent] = []
    current_heading: Optional[str] = None
    has_text = False

    for idx, page in enumerate(reader.pages):
        page_number = idx + 1
        try:
            page_text = page.extract_text() or ""
        except Exception as exc:
            page_text = ""

        # Normalize line endings and filter blank lines
        lines = [line.strip() for line in page_text.splitlines() if line.strip()]
        page_heading = current_heading

        for line in lines:
            detected = detect_heading(line)
            if detected:
                current_heading = detected
                page_heading = detected
                break

        page_str = "\n".join(lines).strip()
        if page_str:
            has_text = True

        parsed_pages.append(
            PageContent(
                page_number=page_number,
                text=page_str,
                heading=page_heading,
            )
        )

    if not has_text:
        raise PDFParsingError("PDF contains no extractable text (document may be scanned or empty).")

    return parsed_pages
