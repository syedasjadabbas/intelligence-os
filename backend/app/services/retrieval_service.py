from dataclasses import dataclass
import logging
import math
import re
from typing import Any, Dict, List, Optional, Tuple
import uuid
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document import Document, DocumentChunk
from app.services.embedding_service import embedding_service

logger = logging.getLogger(__name__)


@dataclass
class SearchResultItem:
    """Represents a single fused search result."""
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    page_number: Optional[int]
    section_heading: Optional[str]
    content: str
    score: float
    vector_rank: Optional[int] = None
    keyword_rank: Optional[int] = None
    rerank_score: Optional[float] = None


def compute_cosine_distance(vec1: List[float], vec2: List[float]) -> float:
    """Compute cosine distance (1.0 - cosine_similarity)."""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 1.0
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 1.0
    similarity = max(-1.0, min(1.0, dot / (norm1 * norm2)))
    return 1.0 - similarity


def compute_keyword_score(content: str, query: str) -> float:
    """Compute term frequency keyword score for dialect-agnostic search."""
    cleaned_content = content.lower()
    query_terms = [t for t in re.findall(r"\w+", query.lower()) if len(t) > 1]
    if not query_terms:
        return 0.0

    score = 0.0
    for term in query_terms:
        # Exact word match count
        matches = len(re.findall(r"\b" + re.escape(term) + r"\b", cleaned_content))
        score += matches * 2.0
        # Substring match count
        if matches == 0 and term in cleaned_content:
            score += 0.5

    return score


class RetrievalService:
    """
    Hybrid Search Retrieval Service combining dense pgvector embeddings,
    PostgreSQL full-text search (ts_rank_cd), and Reciprocal Rank Fusion (RRF).
    """

    def __init__(self, rrf_k: int = settings.RRF_K):
        self.rrf_k = rrf_k

    async def _vector_search_postgres(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        query_embedding: List[float],
        limit: int,
    ) -> List[Tuple[DocumentChunk, str]]:
        """PostgreSQL native vector search using pgvector cosine_distance operator (<=>)."""
        stmt = (
            select(DocumentChunk, Document.title)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(
                DocumentChunk.org_id == org_id,
                DocumentChunk.embedding.isnot(None),
            )
            .order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
            .limit(limit)
        )
        res = await db.execute(stmt)
        return [(row[0], row[1]) for row in res.all()]

    async def _keyword_search_postgres(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        query: str,
        limit: int,
    ) -> List[Tuple[DocumentChunk, str]]:
        """PostgreSQL native full-text search using to_tsvector, plainto_tsquery, and ts_rank_cd."""
        ts_vector = func.to_tsvector("english", DocumentChunk.content)
        ts_query = func.plainto_tsquery("english", query)
        rank_expr = func.ts_rank_cd(ts_vector, ts_query)

        stmt = (
            select(DocumentChunk, Document.title)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(
                DocumentChunk.org_id == org_id,
                ts_vector.op("@@")(ts_query),
            )
            .order_by(rank_expr.desc())
            .limit(limit)
        )
        res = await db.execute(stmt)
        return [(row[0], row[1]) for row in res.all()]

    async def _vector_search_fallback(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        query_embedding: List[float],
        limit: int,
    ) -> List[Tuple[DocumentChunk, str]]:
        """Dialect-agnostic in-memory vector cosine distance search."""
        stmt = (
            select(DocumentChunk, Document.title)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(
                DocumentChunk.org_id == org_id,
                DocumentChunk.embedding.isnot(None),
            )
        )
        res = await db.execute(stmt)
        candidates = res.all()

        scored = []
        for chunk, title in candidates:
            if chunk.embedding is not None:
                # Handle pgvector Vector or list representation
                raw_emb = (
                    chunk.embedding.tolist()
                    if hasattr(chunk.embedding, "tolist")
                    else list(chunk.embedding)
                )
                dist = compute_cosine_distance(raw_emb, query_embedding)
                scored.append((dist, chunk, title))

        scored.sort(key=lambda x: x[0])  # Ascending distance
        return [(item[1], item[2]) for item in scored[:limit]]

    async def _keyword_search_fallback(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        query: str,
        limit: int,
    ) -> List[Tuple[DocumentChunk, str]]:
        """Dialect-agnostic keyword search with term frequency ranking."""
        stmt = (
            select(DocumentChunk, Document.title)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(DocumentChunk.org_id == org_id)
        )
        res = await db.execute(stmt)
        candidates = res.all()

        scored = []
        for chunk, title in candidates:
            score = compute_keyword_score(chunk.content, query)
            if score > 0:
                scored.append((score, chunk, title))

        scored.sort(key=lambda x: x[0], reverse=True)  # Descending score
        return [(item[1], item[2]) for item in scored[:limit]]

    async def hybrid_search(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        query: str,
        top_k: int = 10,
        vector_weight: float = 0.5,
    ) -> List[SearchResultItem]:
        """
        Executes parallel vector and keyword search branches scoped to org_id,
        then fuses and deduplicates the ranked candidate lists via Reciprocal Rank Fusion (RRF).
        """
        branch_limit = top_k * 2

        # 1. Generate query embedding
        query_embedding = await embedding_service.generate_embedding(query)

        # Detect database dialect
        conn = await db.connection()
        is_postgres = conn.dialect.name == "postgresql"

        # 2. Execute Vector Search Branch
        vector_results: List[Tuple[DocumentChunk, str]] = []
        if is_postgres:
            try:
                vector_results = await self._vector_search_postgres(
                    db, org_id, query_embedding, branch_limit
                )
            except Exception as exc:
                logger.warning(
                    f"Postgres vector search failed, using fallback: {exc}"
                )
                vector_results = await self._vector_search_fallback(
                    db, org_id, query_embedding, branch_limit
                )
        else:
            vector_results = await self._vector_search_fallback(
                db, org_id, query_embedding, branch_limit
            )

        # 3. Execute Keyword Search Branch
        keyword_results: List[Tuple[DocumentChunk, str]] = []
        if is_postgres:
            try:
                keyword_results = await self._keyword_search_postgres(
                    db, org_id, query, branch_limit
                )
            except Exception as exc:
                logger.warning(
                    f"Postgres FTS search failed, using fallback: {exc}"
                )
                keyword_results = await self._keyword_search_fallback(
                    db, org_id, query, branch_limit
                )
        else:
            keyword_results = await self._keyword_search_fallback(
                db, org_id, query, branch_limit
            )

        # 4. Reciprocal Rank Fusion (RRF)
        # RRF formula: Score = sum( weight / (RRF_K + rank) )
        candidates: Dict[uuid.UUID, Dict[str, Any]] = {}
        keyword_weight = 1.0 - vector_weight

        # Process vector ranks (1-indexed)
        for rank, (chunk, title) in enumerate(vector_results, start=1):
            chunk_id = chunk.id
            rrf_contrib = vector_weight / (self.rrf_k + rank)

            if chunk_id not in candidates:
                candidates[chunk_id] = {
                    "chunk": chunk,
                    "title": title,
                    "score": rrf_contrib,
                    "vector_rank": rank,
                    "keyword_rank": None,
                }
            else:
                candidates[chunk_id]["score"] += rrf_contrib
                candidates[chunk_id]["vector_rank"] = rank

        # Process keyword ranks (1-indexed)
        for rank, (chunk, title) in enumerate(keyword_results, start=1):
            chunk_id = chunk.id
            rrf_contrib = keyword_weight / (self.rrf_k + rank)

            if chunk_id not in candidates:
                candidates[chunk_id] = {
                    "chunk": chunk,
                    "title": title,
                    "score": rrf_contrib,
                    "vector_rank": None,
                    "keyword_rank": rank,
                }
            else:
                candidates[chunk_id]["score"] += rrf_contrib
                candidates[chunk_id]["keyword_rank"] = rank

        # 5. Sort fused candidates by descending RRF score
        sorted_candidates = sorted(
            candidates.values(),
            key=lambda x: x["score"],
            reverse=True,
        )

        # 6. Format Top K Results with complete citation metadata
        fused_results: List[SearchResultItem] = []
        for item in sorted_candidates[:top_k]:
            chunk: DocumentChunk = item["chunk"]
            fused_results.append(
                SearchResultItem(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    document_title=item["title"],
                    page_number=chunk.page_number,
                    section_heading=chunk.section_heading,
                    content=chunk.content,
                    score=round(item["score"], 6),
                    vector_rank=item["vector_rank"],
                    keyword_rank=item["keyword_rank"],
                )
            )

        return fused_results


# Global singleton retrieval service
retrieval_service = RetrievalService()
