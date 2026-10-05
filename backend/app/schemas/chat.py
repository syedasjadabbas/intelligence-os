from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field, model_validator


class ConversationCreate(BaseModel):
    """Payload to create a new conversation thread."""
    title: Optional[str] = Field(default=None, max_length=255, description="Optional title for conversation")


class MessageResponse(BaseModel):
    """Represents a message inside a conversation."""
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    trace_data: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    """Summary of a conversation thread."""
    id: uuid.UUID
    org_id: uuid.UUID
    user_id: uuid.UUID
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConversationDetailResponse(ConversationResponse):
    """Detailed conversation including its message history."""
    messages: List[MessageResponse] = Field(default_factory=list)


class ChatMessageRequest(BaseModel):
    """Payload for submitting a chat query to a conversation."""
    question: Optional[str] = Field(default=None, description="User's query")
    content: Optional[str] = Field(default=None, description="Alternative field for user query")

    @model_validator(mode="after")
    def validate_query_present(self) -> "ChatMessageRequest":
        text = (self.question or self.content or "").strip()
        if not text:
            raise ValueError("Either 'question' or 'content' must be provided and non-empty.")
        if not self.question:
            self.question = text
        return self


class CitationItem(BaseModel):
    """Source grounding citation linked to a retrieved document chunk."""
    source_index: int
    source_tag: str
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    page_number: Optional[int] = None
    section_heading: Optional[str] = None
    content_snippet: Optional[str] = None


class ChatMessageResponse(BaseModel):
    """Response returned upon message execution in RAG pipeline."""
    conversation_id: uuid.UUID
    user_message_id: uuid.UUID
    assistant_message_id: uuid.UUID
    answer: str
    citations: List[CitationItem] = Field(default_factory=list)
    trace_data: Dict[str, Any] = Field(default_factory=dict)
