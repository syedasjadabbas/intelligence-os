"""
Step 3 Verification Suite: Document Ingestion, PDF Parsing, Context-Aware Chunking,
Background Processing, and Multi-Tenant Isolation.
"""

import asyncio
from io import BytesIO
import os
import sys
import uuid
import httpx
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.core.database import Base, set_session_factory
from app.main import app
from app.models.document import Document, DocumentChunk, DocumentStatus


def create_sample_multi_page_pdf() -> bytes:
    """Generates a valid 2-page PDF document with headings and paragraphs using ReportLab."""
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)

    # Page 1
    c.setFont("Helvetica-Bold", 14)
    c.drawString(72, 750, "# OVERVIEW: INTELLIGENCE OS PLATFORM")
    c.setFont("Helvetica", 10)
    c.drawString(
        72,
        720,
        "Intelligence OS provides enterprise-scale private Retrieval-Augmented Generation.",
    )
    c.drawString(
        72,
        700,
        "All data access paths enforce strict multi-tenant isolation through organization scopes.",
    )
    c.drawString(
        72,
        680,
        "Vector embeddings and text chunks are coupled with cryptographic guarantees and audit logs.",
    )
    c.drawString(
        72,
        650,
        "A hybrid search pipeline pairs BM25 sparse keyword ranking with 1536-dimensional dense vectors.",
    )
    c.showPage()

    # Page 2
    c.setFont("Helvetica-Bold", 14)
    c.drawString(72, 750, "# CHAPTER 2: SECURITY AND CRYPTOGRAPHIC BOUNDARIES")
    c.setFont("Helvetica", 10)
    c.drawString(
        72,
        720,
        "Access control requires OAuth2 signed JWT credentials with explicit role verification.",
    )
    c.drawString(
        72,
        700,
        "Only members with administrative roles may invite users or adjust workspace governance settings.",
    )
    c.drawString(
        72,
        680,
        "Background workers ingest uploaded PDFs into normalized chunks with token boundaries.",
    )
    c.showPage()

    c.save()
    buffer.seek(0)
    return buffer.getvalue()


async def run_ingestion_verification():
    print("=" * 70)
    print("INTELLIGENCE OS - STEP 3 INGESTION VERIFICATION SUITE")
    print("=" * 70)

    # 1. Setup isolated in-memory test database
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestingSessionLocal = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    set_session_factory(TestingSessionLocal)

    # Initialize all model tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[PASS] Test database initialized with full schema.")

    # Override database dependency for FastAPI
    async def override_get_db():
        async with TestingSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        # ----------------------------------------------------------------------
        # Setup: Register Organizations (Org 1 and Org 2 for tenant isolation)
        # ----------------------------------------------------------------------
        print("\n--- Setup: Register Org 1 (Cyberdyne) and Org 2 (Weyland) ---")
        res1 = await client.post(
            "/api/v1/auth/register-org",
            json={
                "org_name": "Cyberdyne Systems",
                "org_slug": "cyberdyne",
                "admin_email": "admin@cyberdyne.com",
                "admin_password": "CyberPassword123!",
            },
        )
        assert res1.status_code == 201
        token_org1 = res1.json()["access_token"]
        org1_id = res1.json()["organization"]["id"]
        headers_org1 = {"Authorization": f"Bearer {token_org1}"}

        res2 = await client.post(
            "/api/v1/auth/register-org",
            json={
                "org_name": "Weyland Yutani",
                "org_slug": "weyland",
                "admin_email": "admin@weyland.com",
                "admin_password": "WeylandPassword123!",
            },
        )
        assert res2.status_code == 201
        token_org2 = res2.json()["access_token"]
        org2_id = res2.json()["organization"]["id"]
        headers_org2 = {"Authorization": f"Bearer {token_org2}"}
        print(f"[PASS] Organizations registered: Cyberdyne ({org1_id}) & Weyland ({org2_id})")

        # ----------------------------------------------------------------------
        # Test 1: Upload Validation (Reject Non-PDF and Corrupted files)
        # ----------------------------------------------------------------------
        print("\n--- Test 1: File Upload Validation Rejection ---")
        # 1. Non-pdf extension
        res_invalid_ext = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("malicious.exe", b"MZexecutabledata", "application/x-msdownload")},
            headers=headers_org1,
        )
        assert res_invalid_ext.status_code == 400
        print(f"[PASS] Non-PDF rejected (400): {res_invalid_ext.json()['detail']}")

        # 2. Corrupted PDF (missing %PDF signature)
        res_corrupt = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("fake.pdf", b"Not a real pdf content", "application/pdf")},
            headers=headers_org1,
        )
        assert res_corrupt.status_code == 400
        print(f"[PASS] Corrupted PDF rejected (400): {res_corrupt.json()['detail']}")

        # ----------------------------------------------------------------------
        # Test 2: Upload Valid Multi-Page PDF & Trigger Background Pipeline
        # ----------------------------------------------------------------------
        print("\n--- Test 2: Upload Multi-Page PDF & Trigger Background Pipeline ---")
        pdf_bytes = create_sample_multi_page_pdf()
        upload_res = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("architecture_whitepaper.pdf", pdf_bytes, "application/pdf")},
            headers=headers_org1,
        )
        assert upload_res.status_code == 202, f"Expected 202, got {upload_res.status_code}"
        upload_data = upload_res.json()
        doc_id = upload_data["id"]
        print(f"[PASS] Document uploaded (202 Accepted): ID {doc_id} | Status: {upload_data['status']}")

        # ----------------------------------------------------------------------
        # Test 3: Polling for Background Processing Completion
        # ----------------------------------------------------------------------
        print("\n--- Test 3: Verify Background Processing Completes ---")
        # Wait up to 10 seconds for background worker to parse and chunk
        completed = False
        doc_details = None
        for attempt in range(20):
            await asyncio.sleep(0.5)
            detail_res = await client.get(
                f"/api/v1/documents/{doc_id}",
                headers=headers_org1,
            )
            assert detail_res.status_code == 200
            doc_details = detail_res.json()
            if doc_details["status"] == "COMPLETED":
                completed = True
                break
            elif doc_details["status"] == "FAILED":
                raise RuntimeError(f"Document ingestion failed: {doc_details['error_message']}")

        assert completed, f"Background processing did not finish in time. Status: {doc_details}"
        assert doc_details["total_chunks"] >= 2, "Expected at least 2 chunks from multi-page document"
        print(f"[PASS] Document status is COMPLETED with {doc_details['total_chunks']} chunks created.")

        # ----------------------------------------------------------------------
        # Test 4: Chunk Metadata & Continuity Inspection
        # ----------------------------------------------------------------------
        print("\n--- Test 4: Verify Chunk Metadata, Page Numbers & Headings ---")
        async with TestingSessionLocal() as session:
            stmt = (
                select(DocumentChunk)
                .where(DocumentChunk.document_id == uuid.UUID(doc_id))
                .order_by(DocumentChunk.chunk_index.asc())
            )
            res_chunks = await session.execute(stmt)
            chunks = res_chunks.scalars().all()

            assert len(chunks) == doc_details["total_chunks"]
            for i, chunk in enumerate(chunks):
                assert chunk.chunk_index == i, f"Chunk index must be sequential. Expected {i}, got {chunk.chunk_index}"
                assert chunk.page_number in [1, 2], f"Invalid page number {chunk.page_number}"
                assert chunk.org_id == uuid.UUID(org1_id), "Chunk org_id must match tenant"
                assert len(chunk.content) > 0, "Chunk content must not be empty"
                print(
                    f"  - Chunk {chunk.chunk_index}: Page {chunk.page_number} | "
                    f"Heading: '{chunk.section_heading}' | Length: {len(chunk.content)} chars"
                )

        print("[PASS] All chunks passed sequential index and page metadata integrity checks.")

        # ----------------------------------------------------------------------
        # Test 5: Strict Multi-Tenant Isolation
        # ----------------------------------------------------------------------
        print("\n--- Test 5: Verify Multi-Tenant Document Isolation ---")
        # Org 2 attempts to get Org 1's document
        res_cross_tenant_get = await client.get(
            f"/api/v1/documents/{doc_id}",
            headers=headers_org2,
        )
        assert res_cross_tenant_get.status_code == 404, f"Expected 404, got {res_cross_tenant_get.status_code}"
        print("[PASS] Org 2 received 404 Not Found when attempting to access Org 1's document.")

        # Org 2 document list should be empty
        res_org2_list = await client.get("/api/v1/documents", headers=headers_org2)
        assert res_org2_list.status_code == 200
        assert len(res_org2_list.json()) == 0, "Org 2 document list must not contain Org 1's documents"
        print("[PASS] Org 2 document list is completely isolated (0 documents).")

        # Org 2 attempts to delete Org 1's document
        res_cross_delete = await client.delete(
            f"/api/v1/documents/{doc_id}",
            headers=headers_org2,
        )
        assert res_cross_delete.status_code == 404
        print("[PASS] Org 2 cannot delete Org 1's document (404 Not Found).")

        # ----------------------------------------------------------------------
        # Test 6: Document Deletion & Cascade Clean-up
        # ----------------------------------------------------------------------
        print("\n--- Test 6: Document Deletion & Cascade Chunk Clean-up ---")
        del_res = await client.delete(
            f"/api/v1/documents/{doc_id}",
            headers=headers_org1,
        )
        assert del_res.status_code == 200
        print(f"[PASS] Document {doc_id} successfully deleted by owner.")

        # Verify chunks are cascaded in database
        async with TestingSessionLocal() as session:
            check_chunks = await session.execute(
                select(DocumentChunk).where(DocumentChunk.document_id == uuid.UUID(doc_id))
            )
            assert len(check_chunks.scalars().all()) == 0
            print("[PASS] All associated DocumentChunk records cleanly cascaded from database.")

    print("\n" + "=" * 70)
    print("ALL STEP 3 INGESTION VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_ingestion_verification())
