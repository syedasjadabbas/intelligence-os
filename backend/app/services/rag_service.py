import asyncio
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple
import uuid
import google.generativeai as genai
from openai import AsyncOpenAI

from app.core.config import settings
from app.services.retrieval_service import SearchResultItem

logger = logging.getLogger(__name__)

CITATION_REGEX = re.compile(r"\[Sources?:?\s*([^\]]+)\]", re.IGNORECASE)

SYSTEM_INSTRUCTION = (
    "You are Intelligence OS. Answer the user's specific question directly and concisely in 1-2 natural sentences using the facts in the provided contexts.\n"
    "- Look inside structured text, tables, and role designations (e.g. 'Role | Name', 'Chief Executive Officer (CEO) | Shahid Mahid').\n"
    "- Handle common abbreviations naturally (e.g. 'CEO' refers to 'Chief Executive Officer').\n"
    "- Cite sources inline using [Source X].\n"
    "- If and ONLY if the context truly contains zero relevant information, reply strictly:\n"
    "  'I cannot find sufficient evidence in the organization's documents to answer this question.'"
)

# Configure Gemini globally using settings.GEMINI_API_KEY
if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip():
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY.strip())
    except Exception as exc:
        logger.warning(f"Failed to configure Gemini globally on startup: {exc}")


class RAGService:
    """
    RAG Generation Service.
    Handles context formatting with numbered source tags, strict grounded system prompting,
    Google Gemini & OpenAI LLM generation, citation extraction and validation,
    insufficient-evidence refusal guardrails, and structured telemetry pipeline tracing.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        gemini_model: Optional[str] = None,
    ):
        self.api_key = api_key
        self.model = model or settings.LLM_MODEL
        self.gemini_api_key = gemini_api_key or settings.GEMINI_API_KEY
        self.gemini_model = gemini_model or settings.GEMINI_MODEL
        self._client: Optional[AsyncOpenAI] = None
        self._cached_key: Optional[str] = None

        if self.gemini_api_key and self.gemini_api_key.strip():
            try:
                genai.configure(api_key=self.gemini_api_key.strip())
            except Exception as exc:
                logger.warning(f"Failed to configure Gemini client in RAGService: {exc}")

    @property
    def client(self) -> Optional[AsyncOpenAI]:
        current_key = self.api_key or settings.OPENAI_API_KEY
        if current_key and current_key.strip():
            if self._client is None or self._cached_key != current_key:
                try:
                    self._client = AsyncOpenAI(api_key=current_key.strip())
                    self._cached_key = current_key
                except Exception as exc:
                    logger.warning(f"Failed to initialize OpenAI client in RAGService: {exc}")
                    self._client = None
        else:
            self._client = None
        return self._client

    def format_context_block(
        self,
        candidates: List[SearchResultItem],
        max_tokens: int = settings.MAX_CONTEXT_TOKENS,
    ) -> Tuple[str, Dict[int, SearchResultItem]]:
        """
        Assembles context block strictly formatted with numbered source tags:
        [Source 1] (Document: {title}, Page: {page}, Section: {heading})
        {content}
        """
        context_blocks = []
        source_map: Dict[int, SearchResultItem] = {}

        # Approximate token count (1 token ~= 4 chars)
        max_chars = max_tokens * 4
        current_chars = 0

        for i, item in enumerate(candidates, start=1):
            page_str = str(item.page_number) if item.page_number is not None else "N/A"
            section_str = item.section_heading if item.section_heading else "General"
            block = (
                f"[Source {i}] (Document: {item.document_title}, Page: {page_str}, Section: {section_str})\n"
                f"{item.content.strip()}"
            )

            if current_chars + len(block) > max_chars and context_blocks:
                logger.info(
                    f"Context reached token budget ({current_chars // 4} tokens). Truncating at {i - 1} sources."
                )
                break

            context_blocks.append(block)
            source_map[i] = item
            current_chars += len(block) + 2

        context_str = "\n\n".join(context_blocks)
        return context_str, source_map

    def validate_and_extract_citations(
        self,
        answer: str,
        source_map: Dict[int, SearchResultItem],
    ) -> Tuple[List[Dict[str, Any]], List[int]]:
        """
        Extracts all [Source X] citations from the generated answer,
        maps each to exact chunk metadata, and flags any unmapped citation numbers.
        """
        mapped_citations: List[Dict[str, Any]] = []
        unmapped_indices: List[int] = []
        seen_indices = set()

        for match in CITATION_REGEX.finditer(answer):
            inner = match.group(1)
            # Split by commas or semicolons to handle multi-source tags (e.g., [Sources 1, 2])
            for part in re.split(r"[,;]", inner):
                part = part.strip()
                # Skip explicit page indicators inside citation tags if any
                if re.search(r"\bpage\b", part, re.IGNORECASE):
                    continue
                nums = re.findall(r"\b\d+\b", part)
                for num_str in nums:
                    idx = int(num_str)
                    if idx in seen_indices:
                        continue
                    seen_indices.add(idx)

                    if idx in source_map:
                        chunk = source_map[idx]
                        citation_record = {
                            "source_index": idx,
                            "source_tag": f"[Source {idx}]",
                            "chunk_id": str(chunk.chunk_id),
                            "document_id": str(chunk.document_id),
                            "document_title": chunk.document_title,
                            "page_number": chunk.page_number,
                            "section_heading": chunk.section_heading,
                            "content_snippet": chunk.content[:200] if chunk.content else "",
                        }
                        mapped_citations.append(citation_record)
                    else:
                        unmapped_indices.append(idx)
                        logger.warning(
                            f"Answer hallucinated citation [Source {idx}] which was not provided in context."
                        )

        return mapped_citations, unmapped_indices

    def _generate_grounded_mock_answer(
        self,
        query: str,
        source_map: Dict[int, SearchResultItem],
    ) -> Tuple[str, bool]:
        """
        Deterministic factual answer generator for offline environments and testing.
        Searches candidate chunks for the exact single sentence directly answering the query.
        Never returns full raw chunk content or dumps paragraphs.
        If no direct factual evidence exists, immediately returns the strict refusal phrase.
        """
        query_lower = query.lower()
        stopwords = {
            "what", "when", "where", "which", "who", "whom", "whose", "why", "how",
            "the", "and", "or", "but", "for", "with", "this", "that", "these", "those",
            "is", "are", "was", "were", "been", "being", "have", "has", "had", "does",
            "did", "doing", "would", "should", "could", "from", "into", "during",
            "before", "after", "above", "below", "to", "of", "in", "on", "at", "by",
            "an", "a", "it", "its", "they", "them", "their", "tell", "me", "about"
        }
        query_words = [
            w for w in re.findall(r"\w+", query_lower)
            if len(w) > 2 and w not in stopwords
        ]

        if not query_words:
            return settings.INSUFFICIENT_EVIDENCE_PHRASE, True

        candidate_matches: List[Tuple[float, int, str]] = []  # (score, source_index, sentence)

        for idx, item in source_map.items():
            # Strip markdown headings and clean chunk content
            clean_content = re.sub(r"^#+[^\n]*\n*", "", item.content, flags=re.MULTILINE).strip()
            # Split strictly by sentence terminators or single newlines
            raw_sentences = re.split(r"(?<=[.!?])\s+|\n+", clean_content)

            for sentence in raw_sentences:
                sent_clean = sentence.strip()
                # Skip empty or overly long raw paragraph dumps
                if not sent_clean or len(sent_clean) < 10 or len(sent_clean) > 350:
                    continue
                # Skip header-like lines
                if sent_clean.startswith("#") or sent_clean.startswith("---"):
                    continue

                sent_lower = sent_clean.lower()

                # Calculate specific keyword / entity overlap
                matched_query_words = 0
                for w in query_words:
                    stem = w[:-1] if w.endswith("s") and len(w) > 3 else w
                    if w in sent_lower or stem in sent_lower:
                        matched_query_words += 1

                # Check subphrase bonus
                subphrase_bonus = 0
                if len(query_words) >= 2:
                    for i in range(len(query_words) - 1):
                        pair = f"{query_words[i]} {query_words[i+1]}"
                        if pair in sent_lower:
                            subphrase_bonus += 2

                score = matched_query_words * 2.0 + subphrase_bonus

                # Require meaningful factual match: at least 2 distinct words or all words if query is short
                min_required = min(2, len(query_words))
                if matched_query_words >= min_required and score >= 2.0:
                    candidate_matches.append((score, idx, sent_clean))

        if not candidate_matches:
            return settings.INSUFFICIENT_EVIDENCE_PHRASE, True

        # Sort descending by match score
        candidate_matches.sort(key=lambda x: x[0], reverse=True)
        best_score, best_idx, best_sentence = candidate_matches[0]

        # Extract only the exact single sentence and format cleanly with [Source X]
        cleaned_sent = best_sentence.rstrip(".!? ")
        concise_answer = f"{cleaned_sent} [Source {best_idx}]."
        return concise_answer, False

    async def _generate_gemini_content(
        self,
        system_instruction: str,
        prompt: str,
    ) -> str:
        """
        Generates answer using genai.GenerativeModel(settings.GEMINI_MODEL) with enforced system instructions.
        Executes via asyncio.to_thread for fast non-blocking execution across environments.
        Supports automatic fallback if a deprecated model name is requested.
        """
        gemini_key = self.gemini_api_key or settings.GEMINI_API_KEY
        if gemini_key and gemini_key.strip():
            try:
                genai.configure(api_key=gemini_key.strip())
            except Exception as exc:
                logger.warning(f"Failed to re-configure Gemini: {exc}")

        primary_model = self.gemini_model or settings.GEMINI_MODEL or "gemini-3.8-flash"
        models_to_try = [primary_model]
        for fallback in ["gemini-3.8-flash", "gemini-flash-latest"]:
            if fallback not in models_to_try:
                models_to_try.append(fallback)

        last_exc = None
        for m_name in models_to_try:
            try:
                gemini_model = genai.GenerativeModel(
                    m_name,
                    system_instruction=system_instruction,
                )
                response = await asyncio.to_thread(
                    gemini_model.generate_content,
                    prompt,
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as exc:
                last_exc = exc
                err_str = str(exc).lower()
                if (
                    "not found" in err_str
                    or "no longer available" in err_str
                    or "quota exceeded" in err_str
                    or "resource_exhausted" in err_str
                    or "429" in err_str
                ):
                    logger.info(
                        f"Gemini model '{m_name}' unavailable ({exc}), attempting next fallback model..."
                    )
                    continue
                else:
                    raise exc

        if last_exc:
            raise last_exc
        return ""

    async def generate_rag_response(
        self,
        original_query: str,
        rewritten_query: str,
        candidates: List[SearchResultItem],
        retrieval_candidate_count: Optional[int] = None,
        retrieval_latency_ms: float = 0.0,
        rerank_latency_ms: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Executes the end-to-end RAG synthesis pipeline:
        1. Context assembly with numbered source tags
        2. Prompting with strict grounding and refusal guardrails via Google Gemini
        3. Citation extraction and validation
        4. Structured pipeline trace telemetry generation with latency metrics
        """
        t_gen_start = time.perf_counter()
        candidate_count = (
            retrieval_candidate_count
            if retrieval_candidate_count is not None
            else len(candidates)
        )

        # Handle empty retrieval
        if not candidates:
            gen_latency_ms = (time.perf_counter() - t_gen_start) * 1000
            total_latency_ms = (
                retrieval_latency_ms + rerank_latency_ms + gen_latency_ms
            )

            trace_data = {
                "original_query": original_query,
                "rewritten_query": rewritten_query,
                "retrieval_candidate_count": 0,
                "reranked_scores": [],
                "selected_sources": [],
                "latency_ms": {
                    "retrieval": round(retrieval_latency_ms, 2),
                    "rerank": round(rerank_latency_ms, 2),
                    "generation": round(gen_latency_ms, 2),
                    "total": round(total_latency_ms, 2),
                },
                "generation_latency_ms": round(gen_latency_ms, 2),
                "is_refusal": True,
            }
            return {
                "answer": settings.INSUFFICIENT_EVIDENCE_PHRASE,
                "citations": [],
                "trace_data": trace_data,
            }

        # 1. Format Context Block
        context_str, source_map = self.format_context_block(candidates)

        answer: str = ""
        is_refusal: bool = False

        # 2. Generate answer with configured LLM Provider (Gemini / OpenAI / Deterministic Fallback)
        gemini_key = self.gemini_api_key or settings.GEMINI_API_KEY
        if settings.LLM_PROVIDER.lower() == "gemini" and gemini_key and gemini_key.strip():
            try:
                user_prompt = (
                    f"Context:\n{context_str}\n\n"
                    f"Question: {rewritten_query}\n\n"
                    "Concise Answer:"
                )
                raw_answer = await self._generate_gemini_content(
                    system_instruction=SYSTEM_INSTRUCTION,
                    prompt=user_prompt,
                )
                if raw_answer:
                    answer = raw_answer.strip()
            except Exception as exc:
                logger.warning(
                    f"Gemini RAG generation failed: {exc}. Falling back to deterministic generator."
                )
                answer = ""
        elif settings.LLM_PROVIDER.lower() == "openai" or (not answer and self.client):
            openai_client = self.client
            if openai_client:
                try:
                    user_prompt = (
                        f"Context:\n{context_str}\n\n"
                        f"Question: {rewritten_query}\n\n"
                        "Concise Answer:"
                    )

                    response = await openai_client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": SYSTEM_INSTRUCTION},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=0.0,
                        max_tokens=200,
                    )
                    raw_answer = response.choices[0].message.content
                    if raw_answer:
                        answer = raw_answer.strip()
                except Exception as exc:
                    logger.warning(
                        f"OpenAI RAG generation failed: {exc}. Falling back to deterministic generator."
                    )
                    answer = ""

        # Fallback to deterministic grounded generator if no answer produced
        if not answer:
            answer, is_refusal = self._generate_grounded_mock_answer(
                query=rewritten_query,
                source_map=source_map,
            )

        # Check refusal guardrail
        if (
            not answer
            or settings.INSUFFICIENT_EVIDENCE_PHRASE.lower() in answer.lower()
            or "cannot find sufficient evidence" in answer.lower()
            or "insufficient evidence" in answer.lower()
            or "does not contain" in answer.lower()
            or "no mention" in answer.lower()
        ):
            answer = settings.INSUFFICIENT_EVIDENCE_PHRASE
            is_refusal = True

        # 3. Citation Extraction & Validation
        citations: List[Dict[str, Any]] = []
        if not is_refusal:
            citations, unmapped = self.validate_and_extract_citations(
                answer, source_map
            )
            # If model produced a grounded answer without citing source tags, map to primary candidate
            if not citations and source_map:
                primary_idx = next(iter(source_map.keys()))
                answer = f"{answer.rstrip('. ')} [Source {primary_idx}]."
                citations, unmapped = self.validate_and_extract_citations(
                    answer, source_map
                )

        gen_latency_ms = (time.perf_counter() - t_gen_start) * 1000
        total_latency_ms = (
            retrieval_latency_ms + rerank_latency_ms + gen_latency_ms
        )

        # 4. Pipeline Tracing Telemetry
        reranked_scores = [
            {
                "chunk_id": str(c.chunk_id),
                "document_id": str(c.document_id),
                "document_title": c.document_title,
                "score": c.score,
                "rerank_score": c.rerank_score,
            }
            for c in candidates
        ]

        selected_sources = [
            {
                "source_index": idx,
                "chunk_id": str(c.chunk_id),
                "document_id": str(c.document_id),
                "document_title": c.document_title,
                "page_number": c.page_number,
                "section_heading": c.section_heading,
            }
            for idx, c in source_map.items()
        ]

        trace_data = {
            "original_query": original_query,
            "rewritten_query": rewritten_query,
            "retrieval_candidate_count": candidate_count,
            "reranked_scores": reranked_scores,
            "selected_sources": selected_sources,
            "latency_ms": {
                "retrieval": round(retrieval_latency_ms, 2),
                "rerank": round(rerank_latency_ms, 2),
                "generation": round(gen_latency_ms, 2),
                "total": round(total_latency_ms, 2),
            },
            "generation_latency_ms": round(gen_latency_ms, 2),
            "is_refusal": is_refusal,
        }

        return {
            "answer": answer,
            "citations": citations,
            "trace_data": trace_data,
        }


# Global singleton RAG service
rag_service = RAGService()
