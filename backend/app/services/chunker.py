from dataclasses import dataclass
import re
from typing import List, Optional
import tiktoken

from app.services.pdf_parser import PageContent


@dataclass
class ChunkResult:
    """Represents a text chunk produced by the context-preserving chunker."""
    chunk_index: int
    content: str
    page_number: int
    section_heading: Optional[str]
    token_count: int


class TextChunker:
    """
    Context-preserving token-based text chunker.
    Splits document pages into semantic chunks while respecting:
    - Page boundaries
    - Paragraph and sentence boundaries
    - Section heading metadata
    - Configured token limits and overlap
    """

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        encoding_name: str = "cl100k_base",
    ):
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be strictly less than chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.encoder = tiktoken.get_encoding(encoding_name)

    def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken cl100k_base."""
        return len(self.encoder.encode(text))

    def _split_into_sentences(self, paragraph: str) -> List[str]:
        """Split a paragraph into sentences preserving ending punctuation."""
        raw_sentences = re.split(r"(?<=[.!?])\s+", paragraph.strip())
        return [s.strip() for s in raw_sentences if s.strip()]

    def _split_oversized_sentence(self, sentence: str) -> List[str]:
        """Fallback split for massive sentences that exceed chunk_size tokens on their own."""
        words = sentence.split()
        sub_chunks: List[str] = []
        current_words: List[str] = []

        for word in words:
            candidate = " ".join(current_words + [word])
            if self.count_tokens(candidate) > self.chunk_size and current_words:
                sub_chunks.append(" ".join(current_words))
                # Retain overlap words
                overlap_words = current_words[-max(1, int(len(current_words) * 0.15)) :]
                current_words = overlap_words + [word]
            else:
                current_words.append(word)

        if current_words:
            sub_chunks.append(" ".join(current_words))
        return sub_chunks

    def chunk_pages(self, pages: List[PageContent]) -> List[ChunkResult]:
        """
        Split a list of PageContent into ChunkResults.
        Retains page_number, section_heading, and sequential chunk_index.
        """
        chunks: List[ChunkResult] = []
        chunk_index = 0

        for page in pages:
            if not page.text.strip():
                continue

            # Split page text into paragraphs
            paragraphs = [p.strip() for p in page.text.split("\n\n") if p.strip()]
            if not paragraphs:
                paragraphs = [line.strip() for line in page.text.split("\n") if line.strip()]

            # Collect sentence units with metadata
            units: List[str] = []
            for para in paragraphs:
                sentences = self._split_into_sentences(para)
                if not sentences:
                    sentences = [para]
                for s in sentences:
                    if self.count_tokens(s) > self.chunk_size:
                        units.extend(self._split_oversized_sentence(s))
                    else:
                        units.append(s)

            # Assemble units into chunks
            current_buffer: List[str] = []

            for unit in units:
                candidate = " ".join(current_buffer + [unit])
                tokens = self.count_tokens(candidate)

                if tokens <= self.chunk_size:
                    current_buffer.append(unit)
                else:
                    if current_buffer:
                        chunk_text = " ".join(current_buffer)
                        chunk_tokens = self.count_tokens(chunk_text)
                        chunks.append(
                            ChunkResult(
                                chunk_index=chunk_index,
                                content=chunk_text,
                                page_number=page.page_number,
                                section_heading=page.heading,
                                token_count=chunk_tokens,
                            )
                        )
                        chunk_index += 1

                        # Calculate overlap units from end of current buffer
                        overlap_buffer: List[str] = []
                        for prev_unit in reversed(current_buffer):
                            test_overlap = " ".join([prev_unit] + overlap_buffer)
                            if self.count_tokens(test_overlap) <= self.chunk_overlap:
                                overlap_buffer.insert(0, prev_unit)
                            else:
                                break

                        current_buffer = overlap_buffer + [unit]
                    else:
                        # Single unit reached size limit
                        current_buffer = [unit]

            if current_buffer:
                chunk_text = " ".join(current_buffer)
                chunks.append(
                    ChunkResult(
                        chunk_index=chunk_index,
                        content=chunk_text,
                        page_number=page.page_number,
                        section_heading=page.heading,
                        token_count=self.count_tokens(chunk_text),
                    )
                )
                chunk_index += 1

        return chunks
