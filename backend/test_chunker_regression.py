"""
Regression Test: Chunker Heading Inheritance and Isolation.
Verifies that:
1. Units preceding a new heading on a page retain the active previous section heading
   instead of prematurely inheriting the first heading found on that page.
2. New section headings cleanly split into isolated chunks rather than being merged
   with unrelated preceding content (such as requirements tables).
"""

import unittest
from app.services.chunker import TextChunker
from app.services.pdf_parser import PageContent


class TestChunkerHeadingIsolation(unittest.TestCase):
    def setUp(self):
        self.chunker = TextChunker(chunk_size=500, chunk_overlap=50)

    def test_heading_inheritance_isolation_across_pages(self):
        # Page 1 defines Section 4: Scope and requirements
        page1_text = (
            "4. Scope and key requirements\n"
            "FR-01: Member profile management.\n"
            "FR-02: Class scheduling and attendance tracking."
        )
        page1 = PageContent(page_number=1, text=page1_text, heading="4. Scope and key requirements")

        # Page 2 has continuation of Section 4 table, followed by Section 5 heading
        page2_text = (
            "FR-03: Online payment processing.\n"
            "NFR-01: System uptime of 99.9%.\n"
            "\n"
            "5. Technology and delivery plan\n"
            "Area: Proposed choice\n"
            "Backend: Python FastAPI REST API\n"
            "Database: PostgreSQL 16 with pgvector"
        )
        page2 = PageContent(page_number=2, text=page2_text, heading="5. Technology and delivery plan")

        chunks = self.chunker.chunk_pages([page1, page2])

        # Verify chunks exist
        self.assertGreater(len(chunks), 1)

        # Find the chunk containing '5. Technology and delivery plan'
        tech_chunks = [c for c in chunks if c.section_heading and "Technology" in c.section_heading]
        self.assertEqual(len(tech_chunks), 1, "Expected exactly one isolated Technology section chunk")

        tech_chunk = tech_chunks[0]
        self.assertIn("Python FastAPI REST API", tech_chunk.content)
        self.assertIn("PostgreSQL", tech_chunk.content)
        # Ensure the preceding requirements (FR-03) were NOT merged into the technology chunk
        self.assertNotIn("FR-03", tech_chunk.content)
        self.assertNotIn("NFR-01", tech_chunk.content)

        # Verify that FR-03 retained the Section 4 heading
        req_chunks = [c for c in chunks if "FR-03" in c.content]
        self.assertEqual(len(req_chunks), 1)
        self.assertIn("4. Scope", req_chunks[0].section_heading)


if __name__ == "__main__":
    unittest.main()
