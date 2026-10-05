from typing import List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class SearchRequest(BaseModel):
    """Hybrid search query request."""
    query: str = Field(..., min_length=1, description="Natural language search query")
    top_k: int = Field(default=5, ge=1, le=50, description="Maximum number of chunks to return")
    vector_weight: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Weight allocated to vector search in RRF (keyword gets 1 - vector_weight)",
    )


class SearchResultItemResponse(BaseModel):
    """Single ranked search result chunk with citation metadata."""
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    page_number: Optional[int] = None
    section_heading: Optional[str] = None
    content: str
    score: float
    vector_rank: Optional[int] = None
    keyword_rank: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class SearchResponse(BaseModel):
    """Hybrid search response payload."""
    query: str
    results: List[SearchResultItemResponse]
    total_candidates: int
