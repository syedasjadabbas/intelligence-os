from datetime import datetime
from typing import Optional
import uuid
from pydantic import BaseModel, ConfigDict

from app.models.document import DocumentStatus


class DocumentBase(BaseModel):
    title: str


class DocumentUploadResponse(BaseModel):
    id: uuid.UUID
    title: str
    status: DocumentStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentResponse(DocumentBase):
    id: uuid.UUID
    org_id: uuid.UUID
    uploaded_by: Optional[uuid.UUID] = None
    file_size_bytes: int
    status: DocumentStatus
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentDetailResponse(DocumentResponse):
    total_chunks: int = 0

    model_config = ConfigDict(from_attributes=True)


class DocumentChunkResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    content: str
    page_number: Optional[int] = None
    section_heading: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
