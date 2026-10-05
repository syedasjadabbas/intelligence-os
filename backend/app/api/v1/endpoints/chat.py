from datetime import datetime, timezone
import logging
import time
from typing import List
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.conversation import Conversation, Message
from app.models.user import User
from app.schemas.chat import (
    ChatMessageRequest,
    ChatMessageResponse,
    CitationItem,
    ConversationCreate,
    ConversationDetailResponse,
    ConversationResponse,
)
from app.services.query_rewriter import query_rewriter
from app.services.rag_service import rag_service
from app.services.reranker_service import reranker_service
from app.services.retrieval_service import retrieval_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Conversation Thread",
    description="Creates a new conversation session scoped to the authenticated user and organization.",
)
async def create_conversation(
    payload: ConversationCreate = ConversationCreate(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """Create a new conversation thread."""
    conv = Conversation(
        org_id=current_user.org_id,
        user_id=current_user.id,
        title=payload.title or "New Conversation",
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


@router.get(
    "/conversations",
    response_model=List[ConversationResponse],
    status_code=status.HTTP_200_OK,
    summary="List Conversations",
    description="Lists all conversations for the authenticated user within their organization.",
)
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ConversationResponse]:
    """List user's conversations within tenant org_id."""
    stmt = (
        select(Conversation)
        .where(
            Conversation.org_id == current_user.org_id,
            Conversation.user_id == current_user.id,
        )
        .order_by(Conversation.updated_at.desc())
    )
    res = await db.execute(stmt)
    return list(res.scalars().all())


@router.get(
    "/conversations/{conv_id}",
    response_model=ConversationDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Conversation Message History",
    description="Retrieves a conversation thread and its complete ordered message history.",
)
async def get_conversation(
    conv_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationDetailResponse:
    """Retrieve message history for a conversation thread."""
    stmt = (
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(
            Conversation.id == conv_id,
            Conversation.org_id == current_user.org_id,
        )
    )
    res = await db.execute(stmt)
    conv = res.scalar_one_or_none()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    # Sort messages chronologically
    sorted_messages = sorted(conv.messages, key=lambda m: m.created_at)
    return ConversationDetailResponse(
        id=conv.id,
        org_id=conv.org_id,
        user_id=conv.user_id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=sorted_messages,
    )


@router.delete(
    "/conversations/{conv_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Conversation Thread",
    description="Deletes a conversation thread and cascades deletion to all associated messages.",
)
async def delete_conversation(
    conv_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a conversation thread."""
    stmt = select(Conversation).where(
        Conversation.id == conv_id,
        Conversation.org_id == current_user.org_id,
    )
    res = await db.execute(stmt)
    conv = res.scalar_one_or_none()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    await db.delete(conv)
    await db.commit()
    return None


@router.post(
    "/conversations/{conv_id}/messages",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Full RAG Chat Query",
    description=(
        "Executes the end-to-end RAG pipeline: Query Rewriting, Multi-Tenant Hybrid Search, "
        "Cross-Encoder Reranking, Grounded LLM Response with Citations, Refusal Guardrail, "
        "and Telemetry Pipeline Tracing."
    ),
)
async def send_chat_message(
    conv_id: uuid.UUID,
    request: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatMessageResponse:
    """
    Submits a user question to an existing conversation thread and executes the RAG pipeline.
    """
    # 1. Fetch conversation verifying multi-tenant ownership
    stmt = (
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(
            Conversation.id == conv_id,
            Conversation.org_id == current_user.org_id,
        )
    )
    res = await db.execute(stmt)
    conv = res.scalar_one_or_none()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    user_query = (request.question or request.content or "").strip()
    history = sorted(conv.messages, key=lambda m: m.created_at)

    # 2. Record user message in DB
    user_msg = Message(
        conversation_id=conv.id,
        role="user",
        content=user_query,
        citations=[],
        trace_data={},
    )
    db.add(user_msg)
    await db.flush()

    # 3. Query Understanding / Rewriting
    rewritten_query = await query_rewriter.rewrite_query(
        query=user_query,
        conversation_history=history,
    )

    # 4. Multi-Tenant Hybrid Search (vector + keyword)
    t_retrieval_start = time.perf_counter()
    candidates = await retrieval_service.hybrid_search(
        db=db,
        org_id=current_user.org_id,
        query=rewritten_query,
        top_k=10,
    )
    retrieval_latency_ms = (time.perf_counter() - t_retrieval_start) * 1000

    # 5. Cross-Encoder Reranker
    t_rerank_start = time.perf_counter()
    reranked_candidates = await reranker_service.rerank(
        query=rewritten_query,
        candidates=candidates,
        top_k=5,
    )
    rerank_latency_ms = (time.perf_counter() - t_rerank_start) * 1000

    # 6. Grounded LLM Generation, Citations & Trace Telemetry
    rag_result = await rag_service.generate_rag_response(
        original_query=user_query,
        rewritten_query=rewritten_query,
        candidates=reranked_candidates,
        retrieval_candidate_count=len(candidates),
        retrieval_latency_ms=retrieval_latency_ms,
        rerank_latency_ms=rerank_latency_ms,
    )

    # 7. Record assistant message in DB
    assistant_msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content=rag_result["answer"],
        citations=rag_result["citations"],
        trace_data=rag_result["trace_data"],
    )
    db.add(assistant_msg)

    # Update conversation title if first message
    if not conv.title or conv.title == "New Conversation":
        conv.title = user_query[:40] + ("..." if len(user_query) > 40 else "")
    conv.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(assistant_msg)

    # 8. Build and return structured response
    citation_items = [CitationItem(**c) for c in rag_result["citations"]]

    return ChatMessageResponse(
        conversation_id=conv.id,
        user_message_id=user_msg.id,
        assistant_message_id=assistant_msg.id,
        answer=rag_result["answer"],
        citations=citation_items,
        trace_data=rag_result["trace_data"],
    )
