import logging
import math
import re
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import settings
from app.services.retrieval_service import SearchResultItem

logger = logging.getLogger(__name__)


def compute_deterministic_cross_score(
    query: str,
    content: str,
    heading: Optional[str] = None,
    title: Optional[str] = None,
) -> float:
    """
    Deterministic cross-attention similarity scoring matrix for offline/local reranking.
    Jointly evaluates query tokens, exact phrase matches, section headings,
    and term proximities against chunk content.
    """
    query_clean = query.lower().strip()
    content_clean = content.lower().strip()
    heading_clean = (heading or "").lower().strip()
    title_clean = (title or "").lower().strip()

    if not query_clean or not content_clean:
        return 0.0

    # 1. Exact query match bonus
    exact_phrase_bonus = 0.0
    if query_clean in content_clean:
        exact_phrase_bonus = 0.45
    elif len(query_clean.split()) > 2:
        # Check subphrases of 2+ words
        q_words = query_clean.split()
        for i in range(len(q_words) - 1):
            subphrase = f"{q_words[i]} {q_words[i+1]}"
            if subphrase in content_clean:
                exact_phrase_bonus = max(exact_phrase_bonus, 0.25)

    # 2. Token coverage & term frequency
    query_tokens = [w for w in re.findall(r"\w+", query_clean) if len(w) > 1]
    if not query_tokens:
        return 0.0

    matched_tokens = 0
    tf_sum = 0
    for token in query_tokens:
        count = len(re.findall(r"\b" + re.escape(token) + r"\b", content_clean))
        if count > 0:
            matched_tokens += 1
            tf_sum += min(count, 5)  # Cap term saturation

    token_coverage = matched_tokens / len(query_tokens)
    tf_score = min(0.3, tf_sum * 0.05)

    # 3. Contextual relevance bonus (Heading and Document Title)
    meta_bonus = 0.0
    for token in query_tokens:
        if token in heading_clean:
            meta_bonus += 0.1
        if token in title_clean:
            meta_bonus += 0.05
    meta_bonus = min(0.2, meta_bonus)

    # 4. Joint score aggregation
    raw_score = (0.4 * token_coverage) + exact_phrase_bonus + tf_score + meta_bonus

    # Sigmoid scaling into [0.0, 1.0] range
    calibrated_score = 1.0 / (1.0 + math.exp(-3.0 * (raw_score - 0.5)))
    return round(float(calibrated_score), 4)


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
                    return reranked
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
            return sorted_candidates[:top_k]
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
        return sorted_candidates[:top_k]

    async def rerank(
        self,
        query: str,
        candidates: List[SearchResultItem],
        top_k: Optional[int] = None,
    ) -> List[SearchResultItem]:
        """
        Reranks a list of candidate chunks against the query.
        Returns top `RERANK_TOP_K` candidates sorted descending by rerank score.
        """
        if not candidates:
            return []

        limit = top_k if top_k is not None else settings.RERANK_TOP_K
        limit = min(limit, len(candidates))

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
