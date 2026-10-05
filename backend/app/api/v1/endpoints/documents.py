import logging
import os
from pathlib import Path
from typing import List
import uuid
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.document import Document, DocumentChunk
from app.models.user import User
from app.schemas.document import (
    DocumentDetailResponse,
    DocumentResponse,
    DocumentUploadResponse,
)
from app.services.document_service import (
    ingest_document,
    process_document_pipeline,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload PDF document for ingestion",
    description="Validates PDF format, securely stores it under tenant directory, and initiates background chunking.",
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentUploadResponse:
    """
    Ingests an enterprise document scoped to the authenticated user's organization.
    Runs parsing and chunking asynchronously via background tasks.
    """
    document = await ingest_document(
        file=file,
        org_id=current_user.org_id,
        user_id=current_user.id,
        db=db,
    )

    # Dispatch asynchronous background processing
    background_tasks.add_task(
        process_document_pipeline,
        document_id=document.id,
        org_id=current_user.org_id,
    )

    return DocumentUploadResponse.model_validate(document)


@router.get(
    "",
    response_model=List[DocumentResponse],
    summary="List tenant documents",
    description="Returns all documents belonging to the caller's organization.",
)
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[DocumentResponse]:
    """Retrieve all documents strictly filtered by the authenticated user's tenant organization."""
    stmt = (
        select(Document)
        .where(Document.org_id == current_user.org_id)
        .order_by(Document.created_at.desc())
    )
    result = await db.execute(stmt)
    documents = result.scalars().all()
    return [DocumentResponse.model_validate(doc) for doc in documents]


@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
    summary="Get document details & chunk count",
    description="Returns metadata, processing status, and total chunk count for a specific document.",
)
async def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentDetailResponse:
    """
    Fetch details for a document.
    Ensures strict tenant isolation (returns 404 if document belongs to another tenant).
    """
    stmt = select(Document).where(
        Document.id == document_id,
        Document.org_id == current_user.org_id,
    )
    result = await db.execute(stmt)
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Count generated chunks
    chunk_count_stmt = select(func.count(DocumentChunk.id)).where(
        DocumentChunk.document_id == document_id,
        DocumentChunk.org_id == current_user.org_id,
    )
    count_res = await db.execute(chunk_count_stmt)
    total_chunks = count_res.scalar() or 0

    detail = DocumentDetailResponse(
        id=document.id,
        org_id=document.org_id,
        uploaded_by=document.uploaded_by,
        title=document.title,
        file_size_bytes=document.file_size_bytes,
        status=document.status,
        error_message=document.error_message,
        created_at=document.created_at,
        updated_at=document.updated_at,
        total_chunks=total_chunks,
    )
    return detail


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete tenant document",
    description="Deletes physical file from disk and cascades deletion of document and its chunks in database.",
)
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Tenant-safe document deletion.
    Cascades to all associated chunks in the database and cleans up disk files.
    """
    stmt = select(Document).where(
        Document.id == document_id,
        Document.org_id == current_user.org_id,
    )
    result = await db.execute(stmt)
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Delete physical file on disk
    if document.file_path and os.path.exists(document.file_path):
        try:
            os.remove(document.file_path)
        except OSError as exc:
            logger.warning(
                f"Failed to delete physical file {document.file_path}: {exc}"
            )

    # Explicitly cascade chunk deletion
    await db.execute(
        delete(DocumentChunk).where(
            DocumentChunk.document_id == document_id,
            DocumentChunk.org_id == current_user.org_id,
        )
    )

    await db.delete(document)
    await db.commit()

    return {
        "status": "success",
        "message": "Document and associated chunks deleted successfully",
        "document_id": str(document_id),
    }
