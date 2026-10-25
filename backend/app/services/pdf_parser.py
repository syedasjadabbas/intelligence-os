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


import re

EXCLUDED_HEADINGS = {
    "ID", "NO", "NO.", "#", "NAME", "STATUS", "DATE", "FIELD", "DETAILS",
    "REQUIREMENT", "NOTE", "NOTES", "VALUE", "TYPE", "PAGE", "TOTAL",
    "ITEM", "ACTION", "DESCRIPTION", "CHECK", "ACCEPTANCE CHECK", "ROLE",
    "ASSIGNEE", "SUMMARY", "OVERVIEW", "COMMENT", "COMMENTS", "RESULT", "RESULTS"
}


def is_running_header_or_footer(line: str) -> bool:
    """Check if line is a common repetitive header/footer (e.g., Page 1, synthetic watermark)."""
    cleaned = line.strip()
    if not cleaned:
        return True
    if re.match(r"^Page\s+\d+(\s+of\s+\d+)?$", cleaned, re.IGNORECASE):
        return True
    if re.match(r"^SAMPLE\s*/\s*SYNTHETIC\s*DATA.*for\s*testing.*$", cleaned, re.IGNORECASE):
        return True
    return False


def detect_heading(line: str) -> Optional[str]:
    """
    Detect whether a text line qualifies as a genuine section heading:
    - Markdown headings (# Heading, ## Subheading)
    - Numbered section titles (e.g. '1. Client overview', '7. Example project records')
    - All-caps titles (e.g. 'CLIENT PROJECT BRIEF', 'EXECUTIVE SUMMARY')
    - Short colon-terminated headers (e.g. 'Key Architecture Findings:')
    Excludes table headers, questions (ending in '?'), and repetitive page watermarks.
    """
    cleaned = line.strip()
    if not cleaned or is_running_header_or_footer(cleaned):
        return None

    # Questions ending in '?' must never be treated as section headings
    if cleaned.endswith("?"):
        return None

    # 1. Markdown syntax
    if cleaned.startswith("#"):
        heading_text = cleaned.lstrip("#").strip()
        if heading_text and heading_text.upper() not in EXCLUDED_HEADINGS:
            return heading_text
        return None

    words = cleaned.split()
    if not (1 <= len(words) <= 12 and len(cleaned) <= 100):
        return None

    # Filter out requirement/test case identifiers (e.g., 'FR-02', 'TC-01')
    if re.match(r"^[A-Z]{1,5}-\d{1,5}$", cleaned):
        return None

    # Exclude table headers & single-word noise
    if cleaned.upper() in EXCLUDED_HEADINGS:
        return None

    # 2. Numbered section heading (e.g., '1. Client overview', '4. Scope and key requirements')
    m_num = re.match(r"^(?:Section\s+\d+:?|\d+(\.\d+)*\.)\s+([A-Za-z0-9\s\-–—/&,]+)$", cleaned, re.IGNORECASE)
    if m_num:
        title = cleaned.rstrip(":.")
        if any(c.isalpha() for c in title) and not title.endswith("?"):
            return title

    # 3. All-caps titles (must have >= 2 words to avoid single-word column headers like 'ID')
    if cleaned.isupper() and any(c.isalpha() for c in cleaned):
        if len(words) >= 2:
            return cleaned.rstrip(":")

    # 4. Short colon-terminated headers (e.g., 'Key Architecture Findings:')
    if cleaned.endswith(":") and not cleaned.endswith(".."):
        candidate = cleaned.rstrip(":")
        if candidate.upper() not in EXCLUDED_HEADINGS and len(words) <= 6:
            return candidate

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
        found_first_on_page = False

        for line in lines:
            detected = detect_heading(line)
            if detected:
                current_heading = detected
                if not found_first_on_page:
                    page_heading = detected
                    found_first_on_page = True

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
