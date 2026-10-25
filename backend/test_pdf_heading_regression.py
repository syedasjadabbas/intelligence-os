"""
Regression tests for PDF heading detection and section-aware chunking.
Verifies that:
1. Ordinary table headers (ID, STATUS, DATE, NAME, REQUIREMENT, etc.) are NOT treated as headings.
2. Legitimate numbered headings (e.g. '7. Example project records', '1. Client overview') are detected.
3. Date intervals and questions are not detected as headings.
4. Chunker properly retains section metadata without pollution.
"""

import unittest
from app.services.pdf_parser import PageContent, detect_heading
from app.services.chunker import TextChunker


class TestPDFHeadingRegression(unittest.TestCase):
    def test_table_headers_excluded(self):
        """Table headers must return None and never be classified as section headings."""
        table_headers = [
            "ID", "STATUS", "DATE", "NO", "NAME", "REQUIREMENT",
            "Acceptance Check", "FIELD", "DETAILS", "NOTE", "TOTAL",
            "ITEM", "ACTION", "DESCRIPTION", "ROLE", "COMMENTS"
        ]
        for th in table_headers:
            detected = detect_heading(th)
            self.assertIsNone(
                detected,
                f"Table header '{th}' was falsely classified as heading '{detected}'"
            )

    def test_legitimate_numbered_headings(self):
        """Valid numbered headings must be correctly detected."""
        valid_headings = [
            ("1. Client overview", "1. Client overview"),
            ("7. Example project records", "7. Example project records"),
            ("4. Scope and key requirements", "4. Scope and key requirements"),
            ("Section 3: Security & Compliance", "Section 3: Security & Compliance"),
            ("2.1. System Architecture", "2.1. System Architecture"),
            ("# Executive Summary", "Executive Summary"),
        ]
        for raw, expected in valid_headings:
            detected = detect_heading(raw)
            self.assertEqual(
                detected, expected,
                f"Expected heading '{expected}' for '{raw}', got '{detected}'"
            )

    def test_non_heading_content_rejected(self):
        """Questions, dates, and plain prose must return None."""
        non_headings = [
            "What is the project code for Northstar?",
            "30 Nov–4 Dec 2026",
            "FR-01",
            "TC-05",
            "This is a standard body paragraph describing project goals.",
            "Page 1 of 5",
            "SAMPLE / SYNTHETIC DATA for testing",
        ]
        for nh in non_headings:
            detected = detect_heading(nh)
            self.assertIsNone(
                detected,
                f"Non-heading content '{nh}' was falsely classified as '{detected}'"
            )

    def test_chunker_section_preservation(self):
        """Chunking text with numbered sections preserves the appropriate section heading."""
        pages = [
            PageContent(
                page_number=1,
                text=(
                    "1. Client overview\n"
                    "Client: Northstar Fitness Studio\n"
                    "Industry: Fitness and wellness\n\n"
                    "2. Project timeline\n"
                    "Duration: 3 months starting Jan 2027\n"
                    "Milestone 1: Prototype completion\n"
                )
            )
        ]
        chunker = TextChunker(chunk_size=100, chunk_overlap=10)
        chunks = chunker.chunk_pages(pages)
        self.assertGreaterEqual(len(chunks), 2)
        headings = [c.section_heading for c in chunks]
        self.assertIn("1. Client overview", headings)
        self.assertIn("2. Project timeline", headings)
        for h in headings:
            self.assertNotIn("ID", h or "")
            self.assertNotIn("STATUS", h or "")


if __name__ == "__main__":
    unittest.main()
