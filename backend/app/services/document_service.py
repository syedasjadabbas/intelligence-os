import logging
import os
from pathlib import Path
from typing import Optional
import uuid
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal, get_session_factory
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.services.chunker import TextChunker
from app.services.embedding_service import embedding_service
from app.services.pdf_parser import PDFParsingError, parse_pdf

logger = logging.getLogger(__name__)


async def validate_pdf_upload(file: UploadFile) -> bytes:
    """
    Validates uploaded file:
    - Extension must be .pdf
    - Content must not be empty and must not exceed MAX_UPLOAD_SIZE_BYTES
    - Magic bytes header must match PDF signature (%PDF-)
    """
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file extension '{ext}'. Only {settings.ALLOWED_EXTENSIONS} files are accepted.",
        )

    # Read content to verify size and signature
    content = await file.read()
    file_size = len(content)

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes).",
        )

    if file_size > settings.MAX_UPLOAD_SIZE_BYTES:
        max_mb = settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {max_mb}MB.",
        )

    # Validate PDF magic header bytes
    if not content.startswith(b"%PDF"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Corrupted or invalid PDF file format (missing %PDF signature).",
        )

    return content


async def ingest_document(
    file: UploadFile,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> Document:
    """
    Validates, saves the file to disk in a tenant-isolated folder, and creates
    the initial Document record with status QUEUED.
    """
    content = await validate_pdf_upload(file)
    document_id = uuid.uuid4()

    # Tenant-isolated file path: uploads/{org_id}/{document_id}.pdf
    org_storage_dir = settings.upload_path / str(org_id)
    org_storage_dir.mkdir(parents=True, exist_ok=True)
    file_path = org_storage_dir / f"{document_id}.pdf"

    # Write file bytes to disk asynchronously
    with open(file_path, "wb") as f:
        f.write(content)

    # Create Document record
    title = file.filename or f"Document_{document_id.hex[:8]}.pdf"
    document = Document(
        id=document_id,
        org_id=org_id,
        uploaded_by=user_id,
        title=title,
        file_path=str(file_path),
        file_size_bytes=len(content),
        status=DocumentStatus.QUEUED,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    return document


async def process_document_pipeline(
    document_id: uuid.UUID,
    org_id: uuid.UUID,
    session_factory=None,
) -> None:
    """
    Background worker pipeline:
    1. Sets status = PROCESSING
    2. Parses PDF pages and extracts heading metadata
    3. Chunks text into semantic chunks with token constraints
    4. Persists DocumentChunk records in the database
    5. Sets status = COMPLETED (or FAILED if parsing/chunking errors occur)
    """
    session_maker = session_factory or get_session_factory()

    async with session_maker() as db:
        stmt = select(Document).where(
            Document.id == document_id,
            Document.org_id == org_id,
        )
        res = await db.execute(stmt)
        document = res.scalar_one_or_none()

        if not document:
            logger.error(
                f"Document {document_id} under org {org_id} not found for background processing."
            )
            return

        # 1. Update status to PROCESSING
        document.status = DocumentStatus.PROCESSING
        await db.commit()

        try:
            # 2. Parse PDF
            pages = parse_pdf(document.file_path)

            # 3. Context-preserving chunking
            chunker = TextChunker(chunk_size=500, chunk_overlap=50)
            chunks = chunker.chunk_pages(pages)

            if not chunks:
                raise PDFParsingError("No valid text chunks could be extracted from PDF.")

            # 4. Generate vector embeddings in batch (1536-dim)
            chunk_texts = [c.content for c in chunks]
            embeddings = await embedding_service.generate_embeddings_batch(chunk_texts)

            # 5. Insert DocumentChunk records with embeddings
            db_chunks = [
                DocumentChunk(
                    id=uuid.uuid4(),
                    org_id=org_id,
                    document_id=document_id,
                    chunk_index=c.chunk_index,
                    content=c.content,
                    page_number=c.page_number,
                    section_heading=c.section_heading,
                    embedding=emb,
                )
                for c, emb in zip(chunks, embeddings)
            ]
            db.add_all(db_chunks)

            # 6. Mark COMPLETED
            document.status = DocumentStatus.COMPLETED
            document.error_message = None
            await db.commit()
            logger.info(
                f"Successfully processed document {document_id}: {len(chunks)} chunks created."
            )

        except Exception as exc:
            # Safely log error without leaking sensitive document text
            logger.error(
                f"Processing failed for document {document_id} (Org {org_id}): {exc}",
                exc_info=True,
            )
            await db.rollback()

            # Mark status = FAILED
            document.status = DocumentStatus.FAILED
            document.error_message = str(exc)
            db.add(document)
            await db.commit()
