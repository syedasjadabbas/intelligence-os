import logging
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.search import (
    SearchRequest,
    SearchResponse,
    SearchResultItemResponse,
)
from app.services.retrieval_service import retrieval_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Hybrid Vector and Keyword Search with RRF",
    description=(
        "Executes parallel dense vector search (pgvector 1536-dim) and full-text keyword search, "
        "fused and deduplicated using Reciprocal Rank Fusion (RRF). "
        "Guarantees strict multi-tenant isolation via the authenticated user's organization."
    ),
)
async def search_documents(
    request: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """
    Hybrid search across the caller's organization documents.
    Blends keyword BM25/FTS with vector cosine similarity.
    """
    logger.info(
        f"Executing hybrid search for tenant {current_user.org_id} (query='{request.query}', top_k={request.top_k})"
    )

    results = await retrieval_service.hybrid_search(
        db=db,
        org_id=current_user.org_id,
        query=request.query,
        top_k=request.top_k,
        vector_weight=request.vector_weight,
    )

    items = [
        SearchResultItemResponse(
            chunk_id=r.chunk_id,
            document_id=r.document_id,
            document_title=r.document_title,
            page_number=r.page_number,
            section_heading=r.section_heading,
            content=r.content,
            score=r.score,
            vector_rank=r.vector_rank,
            keyword_rank=r.keyword_rank,
        )
        for r in results
    ]

    return SearchResponse(
        query=request.query,
        results=items,
        total_candidates=len(items),
    )
