import asyncio
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple
import unicodedata
import uuid
import google.generativeai as genai
from openai import AsyncOpenAI

from app.core.config import settings
from app.services.retrieval_service import SearchResultItem

logger = logging.getLogger(__name__)

CITATION_REGEX = re.compile(r"\[Sources?:?\s*([^\]]+)\]", re.IGNORECASE)

SYSTEM_INSTRUCTION = (
    "You are Intelligence OS. Answer the user's specific question directly and concisely in 1-2 natural sentences using the facts in the provided contexts.\n"
    "- Match organizational roles, designations, and job titles flexibly. For example:\n"
    "  * 'supervisor' matches 'Production & Floor Supervisor'\n"
    "  * 'manager' matches 'Operations / Branch Manager'\n"
    "  * 'cashier' or 'finance' matches 'Head Cashier / Finance Officer'\n"
    "  * 'CEO' matches 'Chief Executive Officer'\n"
    "- Extract the exact person's name or metric associated with the matched role/entity.\n"
    "- Always cite sources inline using [Source X].\n"
    "- If and ONLY if the provided context contains truly zero relevant information or mentions of the topic, reply strictly:\n"
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

    @staticmethod
    def sanitize_model_name(model_name: Optional[str]) -> str:
        """
        Sanitizes model name by trimming whitespace, stripping any 'models/' prefix,
        and ensuring clean identifier format.
        """
        if not model_name:
            return "gemini-2.5-flash"
        cleaned = model_name.strip().strip("'\"")
        if cleaned.lower().startswith("models/"):
            cleaned = cleaned[7:]
        return cleaned or "gemini-2.5-flash"

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
        self.gemini_model = self.sanitize_model_name(gemini_model or settings.GEMINI_MODEL)
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

    def _generate_fallback_answer(
        self,
        query: str,
        source_map: Dict[int, SearchResultItem],
    ) -> Tuple[str, bool]:
        """
        Deterministic factual answer generator with structured pair extraction.
        Parses candidate chunks line-by-line:
          a. Delimiter pairs: split on ':' or '|' into (key, val).
          b. Same-line table pairs: regex match Key Value.
          c. Multi-line card pairs: line i is concise label (<= 6 words), line i+1 is value (<= 10 words).
        Scores pairs against query tokens (stems, consecutive bigrams, numeric/personnel bonuses).
        Falls back to sentence-level factual matcher or refusal phrase if ungrounded.
        """
        query_lower = query.lower()
        stopwords = {
            "what", "when", "where", "which", "who", "whom", "whose", "why", "how",
            "the", "and", "or", "but", "for", "with", "this", "that", "these", "those",
            "is", "are", "was", "were", "been", "being", "have", "has", "had", "does",
            "did", "doing", "would", "should", "could", "from", "into", "during",
            "before", "after", "above", "below", "to", "of", "in", "on", "at", "by",
            "an", "a", "it", "its", "they", "them", "their", "tell", "me", "about",
        }
        query_words = [
            w for w in re.findall(r"\w+", query_lower)
            if len(w) > 2 and w not in stopwords
        ]

        if not query_words:
            return settings.INSUFFICIENT_EVIDENCE_PHRASE, True

        # Extract entity if specified in query (e.g., 'of Lonetex' or 'Lonetex\'s')
        entity: Optional[str] = None
        m_entity = re.search(r"\bof\s+([A-Za-z0-9_\s]+?)(?:\?|$|\.|\,)", query, re.IGNORECASE)
        if m_entity:
            ent = m_entity.group(1).strip()
            if ent.lower() not in {"this", "that", "the", "it", "them", "these", "those"}:
                entity = ent.title()
        if not entity:
            m_entity = re.search(r"\b([A-Za-z0-9_-]+)\'s\b", query, re.IGNORECASE)
            if m_entity:
                entity = m_entity.group(1).strip().title()

        entity_words = set(re.findall(r"\w+", entity.lower())) if entity else set()
        attr_words = [w for w in query_words if w not in entity_words]

        # 1. Structured Pair Extraction
        pair_candidates: List[Tuple[str, str, int, str]] = []

        for idx, item in source_map.items():
            lines = [
                unicodedata.normalize("NFKD", line.strip())
                for line in item.content.splitlines()
                if line.strip()
            ]

            for i in range(len(lines)):
                line = lines[i]

                # a. Delimiter pairs: split on ':' or '|' into (key, val)
                for delim in [":", "|"]:
                    if delim in line:
                        parts = line.split(delim, 1)
                        k, v = parts[0].strip(), parts[1].strip()
                        if k and v:
                            pair_candidates.append((k, v, idx, "delim"))

                # b. Same-line table pairs: regex match Key Value
                # e.g., 'Total Active Workforce 35 Team Members' or 'Chief Executive Officer (CEO) Shahid Mahid'
                m_same = re.match(
                    r"^([A-Za-z\s\(\)/&]+?)\s{1,4}(\d+.*|PKR\b.*|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)$",
                    line,
                )
                if m_same:
                    k, v = m_same.group(1).strip(), m_same.group(2).strip()
                    if k and v and len(k.split()) >= 2:
                        pair_candidates.append((k, v, idx, "same_line"))

                # c. Multi-line card pairs: when line i is concise label/header (<= 6 words)
                # and line i+1 contains the value (<= 10 words, numbers, or designations)
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    if len(line.split()) <= 6 and not line.startswith("#") and not line.startswith("---"):
                        if len(next_line.split()) <= 10 and not next_line.startswith("#"):
                            pair_candidates.append((line, next_line, idx, "multiline"))

        # Score extracted pairs against query tokens (matching stems, consecutive bigrams, concrete numeric/personnel bonuses)
        scored_pairs: List[Tuple[float, str, str, int, str]] = []
        for k, v, idx, ctype in pair_candidates:
            k_lower = k.lower()
            v_lower = v.lower()
            combined = f"{k_lower} {v_lower}"

            matches = 0
            attr_matches = 0
            for w in query_words:
                stem = w[:-1] if w.endswith("s") and len(w) > 3 else w
                if w in k_lower or stem in k_lower:
                    matches += 1
                    if w in attr_words or stem in attr_words:
                        attr_matches += 1

            if attr_words and attr_matches == 0:
                continue
            if matches == 0:
                continue

            score = matches * 3.0

            # Consecutive bigrams match
            if len(query_words) >= 2:
                for j in range(len(query_words) - 1):
                    pair = f"{query_words[j]} {query_words[j+1]}"
                    if pair in k_lower or pair in combined:
                        score += 3.0

            # Concrete numeric / personnel bonuses
            is_name = bool(re.match(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+$", v))
            if (
                re.search(r"\d+", v)
                or re.search(r"\b(personnel|members|team|categories|cube|hours|scale|pkr)\b", v_lower)
                or is_name
            ):
                score += 4.0

            scored_pairs.append((score, k, v, idx, ctype))

        scored_pairs.sort(key=lambda x: x[0], reverse=True)

        if scored_pairs:
            best_pair = scored_pairs[0]
            k, v, source_idx = best_pair[1], best_pair[2], best_pair[3]
            clean_key = re.sub(r"^[#*\-\s]+", "", k).strip().lower()
            clean_val = re.sub(r"^[#*\-\s]+", "", v).strip().rstrip(".,; ")
            val_parts = clean_val.split()
            if (
                len(val_parts) >= 2
                and val_parts[0].isdigit()
                and val_parts[1].lower() in {"personnel", "team members", "members", "categories", "employees", "staff"}
            ):
                clean_val_formatted = f"{val_parts[0]} {val_parts[1].lower()}" + (
                    " " + " ".join(val_parts[2:]) if len(val_parts) > 2 else ""
                )
            else:
                clean_val_formatted = clean_val

            if entity and entity.lower() not in clean_key:
                sentence = f"The {clean_key} of {entity} is {clean_val_formatted} [Source {source_idx}]."
            else:
                sentence = f"The {clean_key} is {clean_val_formatted} [Source {source_idx}]."
            return sentence, False

        # 2. Sentence-level factual matcher fallback
        candidate_matches: List[Tuple[float, int, str]] = []

        for idx, item in source_map.items():
            clean_content = re.sub(r"^#+[^\n]*\n*", "", item.content, flags=re.MULTILINE).strip()
            raw_sentences = re.split(r"(?<=[.!?])\s+|\n+", clean_content)

            for sentence in raw_sentences:
                sent_clean = sentence.strip()
                if not sent_clean or len(sent_clean) < 10 or len(sent_clean) > 350:
                    continue
                if sent_clean.startswith("#") or sent_clean.startswith("---"):
                    continue

                sent_lower = sent_clean.lower()

                matched_query_words = 0
                for w in query_words:
                    stem = w[:-1] if w.endswith("s") and len(w) > 3 else w
                    if w in sent_lower or stem in sent_lower:
                        matched_query_words += 1

                subphrase_bonus = 0
                if len(query_words) >= 2:
                    for i in range(len(query_words) - 1):
                        pair = f"{query_words[i]} {query_words[i+1]}"
                        if pair in sent_lower:
                            subphrase_bonus += 2

                score = matched_query_words * 2.0 + subphrase_bonus

                min_required = min(2, len(query_words))
                if matched_query_words >= min_required and score >= 2.0:
                    candidate_matches.append((score, idx, sent_clean))

        if not candidate_matches:
            return settings.INSUFFICIENT_EVIDENCE_PHRASE, True

        candidate_matches.sort(key=lambda x: x[0], reverse=True)
        best_score, best_idx, best_sentence = candidate_matches[0]
        cleaned_sent = best_sentence.rstrip(".!? ")
        concise_answer = f"{cleaned_sent} [Source {best_idx}]."
        return concise_answer, False

    def _generate_grounded_mock_answer(
        self,
        query: str,
        source_map: Dict[int, SearchResultItem],
    ) -> Tuple[str, bool]:
        """Compatibility wrapper forwarding to _generate_fallback_answer."""
        return self._generate_fallback_answer(query, source_map)

    async def _generate_gemini_content(
        self,
        system_instruction: str,
        prompt: str,
    ) -> str:
        """
        Generates answer using genai.GenerativeModel(settings.GEMINI_MODEL) with enforced system instructions.
        Executes via asyncio.to_thread for fast non-blocking execution across environments.
        Supports automatic fallback if a model is deprecated (404) or quota is exhausted (429).
        """
        gemini_key = self.gemini_api_key or settings.GEMINI_API_KEY
        if gemini_key and gemini_key.strip():
            try:
                genai.configure(api_key=gemini_key.strip())
            except Exception as exc:
                logger.warning(f"Failed to re-configure Gemini: {exc}")

        primary_model = self.sanitize_model_name(self.gemini_model or settings.GEMINI_MODEL)
        models_to_try = [primary_model]
        candidate_fallbacks = [
            "gemini-2.5-flash",
            "gemini-3.5-flash",
            "gemini-3.7-flash",
            "gemini-3.6-flash",
            "gemini-flash-lite-latest",
            "gemini-3.8-flash",
            "gemini-flash-latest",
        ]
        for fallback in candidate_fallbacks:
            clean_fb = self.sanitize_model_name(fallback)
            if clean_fb not in models_to_try:
                models_to_try.append(clean_fb)

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
                    "404" in err_str
                    or "not found" in err_str
                    or "no longer available" in err_str
                    or "deprecated" in err_str
                    or "429" in err_str
                    or "quota exceeded" in err_str
                    or "resource_exhausted" in err_str
                    or "resourceexhausted" in err_str
                    or "rate limit" in err_str
                    or "unavailable" in err_str
                    or "503" in err_str
                ):
                    logger.info(
                        f"Gemini model '{m_name}' unavailable ({exc}), attempting next fallback model..."
                    )
                    continue
                else:
                    logger.warning(
                        f"Gemini model '{m_name}' encountered error ({exc}), attempting next fallback model..."
                    )
                    continue

        if last_exc:
            logger.warning(f"All Gemini models exhausted or failed: {last_exc}")
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
            answer, is_refusal = self._generate_fallback_answer(
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
