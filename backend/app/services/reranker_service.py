import logging
import math
import re
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import settings
from app.services.retrieval_service import SearchResultItem

logger = logging.getLogger(__name__)


STOPWORDS = {
    "what", "when", "where", "which", "who", "whom", "whose", "why", "how",
    "the", "and", "or", "but", "for", "with", "this", "that", "these", "those",
    "is", "are", "was", "were", "been", "being", "have", "has", "had", "does",
    "did", "doing", "would", "should", "could", "from", "into", "during",
    "before", "after", "above", "below", "to", "of", "in", "on", "at", "by",
    "an", "a", "it", "its", "they", "them", "their", "tell", "me", "about",
}


def compute_deterministic_cross_score(
    query: str,
    content: str,
    heading: Optional[str] = None,
    title: Optional[str] = None,
) -> float:
    """
    Deterministic cross-attention similarity scoring matrix for offline/local reranking.
    Jointly evaluates salient query tokens (accounting for stop words), exact phrase matches,
    document title/entity propagation, and section headings against chunk content.
    """
    query_clean = query.lower().strip()
    content_clean = content.lower().strip()
    heading_clean = (heading or "").lower().strip()
    title_clean = (title or "").lower().strip()

    if not query_clean or not content_clean:
        return 0.0

    # 1. Exact query / phrase match bonus
    exact_phrase_bonus = 0.0
    if query_clean in content_clean:
        exact_phrase_bonus = 0.45
    elif len(query_clean.split()) > 2:
        q_words = query_clean.split()
        for i in range(len(q_words) - 1):
            subphrase = f"{q_words[i]} {q_words[i+1]}"
            if subphrase in content_clean:
                exact_phrase_bonus = max(exact_phrase_bonus, 0.25)

    # 2. Extract salient content tokens (filtering common interrogatives and stop words)
    all_tokens = [w for w in re.findall(r"\w+", query_clean) if len(w) > 1]
    content_tokens = [w for w in all_tokens if w not in STOPWORDS] or all_tokens
    if not content_tokens:
        return 0.0

    matched_content_tokens = 0.0
    content_hits = 0
    tf_sum = 0

    for token in content_tokens:
        stem = token[:-1] if token.endswith("s") and len(token) > 3 else token
        in_content = token in content_clean or stem in content_clean
        in_title = token in title_clean or stem in title_clean
        in_heading = token in heading_clean or stem in heading_clean

        if in_content:
            matched_content_tokens += 1.0
            content_hits += 1
            # Term saturation in chunk body
            count = len(re.findall(r"\b" + re.escape(token) + r"\b", content_clean))
            tf_sum += min(max(count, 1), 5)
        elif in_title or in_heading:
            # Token satisfied by document title or section heading context
            matched_content_tokens += 0.85

    token_coverage = matched_content_tokens / len(content_tokens)
    tf_score = min(0.25, tf_sum * 0.05)

    # 3. Contextual relevance bonus (Heading and Document Title)
    meta_bonus = 0.0
    for token in content_tokens:
        if token in heading_clean:
            meta_bonus += 0.1
        if token in title_clean:
            meta_bonus += 0.08
    meta_bonus = min(0.25, meta_bonus)

    # Specific chunk content term bonus (e.g. role title or specific metric matched in chunk)
    role_bonus = 0.0
    for token in content_tokens:
        if (token in content_clean) and (token not in title_clean):
            role_bonus += 0.20
    role_bonus = min(0.30, role_bonus)

    # 4. Joint score aggregation
    raw_score = (
        (0.45 * token_coverage)
        + exact_phrase_bonus
        + tf_score
        + meta_bonus
        + role_bonus
    )

    # Sigmoid scaling into [0.0, 1.0] range
    calibrated_score = 1.0 / (1.0 + math.exp(-3.2 * (raw_score - 0.42)))
    return round(float(calibrated_score), 4)


def deduplicate_candidates(candidates: List[SearchResultItem]) -> List[SearchResultItem]:
    """
    Deduplicates candidates with identical or near-identical content so multiple
    document uploads or chunk overlaps do not crowd out distinct informative chunks.
    """
    seen_signatures = set()
    deduped = []
    for c in candidates:
        sig = re.sub(r"\s+", " ", c.content.strip().lower())[:160]
        if sig not in seen_signatures:
            seen_signatures.add(sig)
            deduped.append(c)
    return deduped


class RerankerService:
    """
    Pluggable Cross-Encoder Reranking Service.
    Supports:
    1. sentence-transformers CrossEncoder (if installed locally)
    2. Cohere Rerank API (if COHERE_API_KEY is configured)
    3. Deterministic cross-encoder matrix for offline local testing
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        cohere_api_key: Optional[str] = None,
    ):
        self.model_name = model_name or settings.RERANKER_MODEL
        self.cohere_api_key = (
            cohere_api_key if cohere_api_key is not None else settings.COHERE_API_KEY
        )
        self._cross_encoder = None
        self._init_cross_encoder()

    def _init_cross_encoder(self):
        """Attempts to load sentence-transformers CrossEncoder if available."""
        try:
            from sentence_transformers import CrossEncoder

            self._cross_encoder = CrossEncoder(self.model_name)
            logger.info(f"Loaded sentence-transformers CrossEncoder: {self.model_name}")
        except Exception as exc:
            logger.debug(
                f"CrossEncoder model not loaded ({exc}). Using Cohere or deterministic reranker."
            )
            self._cross_encoder = None

    async def _rerank_cohere(
        self, query: str, candidates: List[SearchResultItem], top_k: int
    ) -> Optional[List[SearchResultItem]]:
        """Rerank candidates using Cohere Rerank API."""
        if not self.cohere_api_key or not self.cohere_api_key.strip():
            return None

        try:
            docs = [c.content for c in candidates]
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(
                    "https://api.cohere.com/v2/rerank",
                    headers={
                        "Authorization": f"Bearer {self.cohere_api_key.strip()}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "rerank-v3.5",
                        "query": query,
                        "documents": docs,
                        "top_n": top_k,
                    },
                )
                if res.status_code == 200:
                    data = res.json()
                    results = data.get("results", [])
                    reranked: List[SearchResultItem] = []
                    for r in results:
                        idx = r["index"]
                        relevance = float(r["relevance_score"])
                        candidate = candidates[idx]
                        candidate.rerank_score = round(relevance, 4)
                        reranked.append(candidate)
                    deduped = deduplicate_candidates(reranked)
                    return deduped[:top_k]
                else:
                    logger.warning(
                        f"Cohere Rerank API error {res.status_code}: {res.text}"
                    )
        except Exception as exc:
            logger.warning(f"Cohere reranking failed: {exc}")

        return None

    def _rerank_cross_encoder(
        self, query: str, candidates: List[SearchResultItem], top_k: int
    ) -> Optional[List[SearchResultItem]]:
        """Rerank candidates using loaded local CrossEncoder."""
        if self._cross_encoder is None:
            return None

        try:
            pairs = [[query, c.content] for c in candidates]
            scores = self._cross_encoder.predict(pairs)
            for candidate, score in zip(candidates, scores):
                candidate.rerank_score = round(float(score), 4)

            sorted_candidates = sorted(
                candidates,
                key=lambda x: x.rerank_score if x.rerank_score is not None else 0.0,
                reverse=True,
            )
            deduped = deduplicate_candidates(sorted_candidates)
            return deduped[:top_k]
        except Exception as exc:
            logger.warning(f"Local CrossEncoder inference failed: {exc}")

        return None

    def _rerank_deterministic(
        self, query: str, candidates: List[SearchResultItem], top_k: int
    ) -> List[SearchResultItem]:
        """Deterministic cross-scoring algorithm for test suite and offline environments."""
        for c in candidates:
            score = compute_deterministic_cross_score(
                query=query,
                content=c.content,
                heading=c.section_heading,
                title=c.document_title,
            )
            c.rerank_score = score

        # Sort candidates descending by rerank score
        sorted_candidates = sorted(
            candidates,
            key=lambda x: x.rerank_score if x.rerank_score is not None else 0.0,
            reverse=True,
        )
        deduped = deduplicate_candidates(sorted_candidates)
        return deduped[:top_k]

    async def rerank(
        self,
        query: str,
        candidates: List[SearchResultItem],
        top_k: Optional[int] = None,
    ) -> List[SearchResultItem]:
        """
        Reranks a list of candidate chunks against the query.
        Ensures moderate candidates are preserved and returns top 3-5 candidates
        without aggressive margin pruning.
        """
        if not candidates:
            return []

        limit = top_k if top_k is not None else settings.RERANK_TOP_K
        # Ensure at least 3 candidates are retained if available, up to limit
        limit = max(min(3, len(candidates)), min(limit, len(candidates)))

        # 1. Try Cohere API
        cohere_results = await self._rerank_cohere(query, candidates, limit)
        if cohere_results is not None:
            return cohere_results

        # 2. Try Local CrossEncoder
        local_results = self._rerank_cross_encoder(query, candidates, limit)
        if local_results is not None:
            return local_results

        # 3. Deterministic cross-encoder scoring matrix
        return self._rerank_deterministic(query, candidates, limit)


# Global singleton reranker service
reranker_service = RerankerService()
