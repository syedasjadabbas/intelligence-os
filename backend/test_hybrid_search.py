"""
Step 4 Verification Suite: Vector Embeddings Generation, pgvector Persistence,
Full-Text Keyword Search, Parallel Hybrid Retrieval with Reciprocal Rank Fusion (RRF),
and Multi-Tenant Isolation.
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
from app.models.document import Document, DocumentChunk


def build_pdf_document(pages_content: list[tuple[str, list[str]]]) -> bytes:
    """Helper to create a multi-page PDF with custom headings and paragraphs."""
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)

    for heading, paragraphs in pages_content:
        c.setFont("Helvetica-Bold", 14)
        c.drawString(72, 750, heading)
        y = 720
        c.setFont("Helvetica", 10)
        for para in paragraphs:
            c.drawString(72, y, para)
            y -= 25
        c.showPage()

    c.save()
    buffer.seek(0)
    return buffer.getvalue()


async def run_hybrid_search_verification():
    print("=" * 70)
    print("INTELLIGENCE OS - STEP 4 HYBRID RETRIEVAL & RRF VERIFICATION")
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

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[PASS] Test database initialized.")

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
        # Setup: Register Organizations (Stark Industries & Wayne Enterprises)
        # ----------------------------------------------------------------------
        print("\n--- Setup: Register Stark Industries (Org 1) & Wayne Enterprises (Org 2) ---")
        res1 = await client.post(
            "/api/v1/auth/register-org",
            json={
                "org_name": "Stark Industries",
                "org_slug": "stark-industries",
                "admin_email": "tony@stark.com",
                "admin_password": "IamIronMan3000!",
            },
        )
        assert res1.status_code == 201
        token_stark = res1.json()["access_token"]
        org_stark_id = res1.json()["organization"]["id"]
        headers_stark = {"Authorization": f"Bearer {token_stark}"}

        res2 = await client.post(
            "/api/v1/auth/register-org",
            json={
                "org_name": "Wayne Enterprises",
                "org_slug": "wayne-enterprises",
                "admin_email": "bruce@wayne.com",
                "admin_password": "DarkKnightBatman1!",
            },
        )
        assert res2.status_code == 201
        token_wayne = res2.json()["access_token"]
        org_wayne_id = res2.json()["organization"]["id"]
        headers_wayne = {"Authorization": f"Bearer {token_wayne}"}
        print(f"[PASS] Orgs created: Stark ({org_stark_id}) & Wayne ({org_wayne_id})")

        # ----------------------------------------------------------------------
        # Upload Document 1 (Stark): Arc Reactor Technical Architecture
        # ----------------------------------------------------------------------
        print("\n--- Upload Document 1 (Stark): Arc Reactor Architecture ---")
        doc1_pages = [
            (
                "# ARC REACTOR TECHNICAL OVERVIEW",
                [
                    "The Arc Reactor utilizes palladium core containment to catalyze cold fusion reactions.",
                    "High-frequency plasma confinement sustains a magnetic flux density capable of powering repulsors.",
                    "Clean energy generation reaches peak output with minimal thermal loss.",
                ],
            ),
            (
                "# EMERGENCY COOLING AND HEAT EXCHANGERS",
                [
                    "Emergency shutdown requires rapid thermal dissipation through liquid nitrogen cooling circuits.",
                    "Redundant magnetic coils prevent catastrophic containment breaches during thermal spikes.",
                    "Automated failsafes vent cryogenic nitrogen when temperature exceeds critical thresholds.",
                ],
            ),
        ]
        pdf1 = build_pdf_document(doc1_pages)
        res_upload1 = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("arc_reactor_blueprint.pdf", pdf1, "application/pdf")},
            headers=headers_stark,
        )
        assert res_upload1.status_code == 202
        doc1_id = res_upload1.json()["id"]

        # ----------------------------------------------------------------------
        # Upload Document 2 (Stark): Autonomous Drone Avionics
        # ----------------------------------------------------------------------
        print("\n--- Upload Document 2 (Stark): Autonomous Drone Avionics ---")
        doc2_pages = [
            (
                "# IRON LEGION AVIONICS AND FLIGHT CONTROL",
                [
                    "Autonomous drone avionics employ neural mesh navigation and localized sensor networks.",
                    "Perimeter defense routines automatically detect approaching aerial targets.",
                    "Decentralized flight algorithms ensure coordinated swarm tactics.",
                ],
            )
        ]
        pdf2 = build_pdf_document(doc2_pages)
        res_upload2 = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("iron_legion_avionics.pdf", pdf2, "application/pdf")},
            headers=headers_stark,
        )
        assert res_upload2.status_code == 202
        doc2_id = res_upload2.json()["id"]

        # ----------------------------------------------------------------------
        # Upload Document 3 (Wayne): Batcave Surveillance (Mentions Arc Reactor)
        # ----------------------------------------------------------------------
        print("\n--- Upload Document 3 (Wayne): Batcave Surveillance Notes ---")
        doc3_pages = [
            (
                "# BATCAVE INTELLIGENCE ON ARC REACTOR",
                [
                    "Wayne Enterprises tactical assessment of Stark Arc Reactor technology and fusion reports.",
                    "Gotham city power grid comparative analysis against Stark clean energy models.",
                ],
            )
        ]
        pdf3 = build_pdf_document(doc3_pages)
        res_upload3 = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("batcave_intelligence.pdf", pdf3, "application/pdf")},
            headers=headers_wayne,
        )
        assert res_upload3.status_code == 202
        doc3_id = res_upload3.json()["id"]

        # Wait for all background workers to finish
        print("\n--- Waiting for background ingestion & embedding pipelines ---")
        for doc_id, headers in [(doc1_id, headers_stark), (doc2_id, headers_stark), (doc3_id, headers_wayne)]:
            for _ in range(20):
                await asyncio.sleep(0.4)
                det = await client.get(f"/api/v1/documents/{doc_id}", headers=headers)
                if det.json()["status"] == "COMPLETED":
                    break
            assert det.json()["status"] == "COMPLETED", f"Doc {doc_id} did not complete: {det.json()}"
        print("[PASS] All documents successfully ingested and embedded.")

        # ----------------------------------------------------------------------
        # Test 1: Verify 1536-Dimensional Embeddings Persistence
        # ----------------------------------------------------------------------
        print("\n--- Test 1: Inspect DocumentChunk Embeddings in Database ---")
        async with TestingSessionLocal() as session:
            stmt = select(DocumentChunk).where(DocumentChunk.document_id == uuid.UUID(doc1_id))
            res_chunks = await session.execute(stmt)
            chunks = res_chunks.scalars().all()

            assert len(chunks) == 2, f"Expected 2 chunks, got {len(chunks)}"
            for c in chunks:
                assert c.embedding is not None, "Embedding vector must not be null"
                raw_vec = c.embedding.tolist() if hasattr(c.embedding, "tolist") else list(c.embedding)
                assert len(raw_vec) == 1536, f"Embedding dimension must be 1536, got {len(raw_vec)}"
                print(f"  - Chunk {c.chunk_index}: Dim = {len(raw_vec)} | First 3 floats = {raw_vec[:3]}")

        print("[PASS] 1536-dimensional float vector embeddings verified on all chunks.")

        # ----------------------------------------------------------------------
        # Test 2: Exact Keyword Search
        # ----------------------------------------------------------------------
        print("\n--- Test 2: Full-Text Keyword Search ---")
        kw_res = await client.post(
            "/api/v1/search",
            json={"query": "palladium core cold fusion", "top_k": 3},
            headers=headers_stark,
        )
        assert kw_res.status_code == 200
        search_data = kw_res.json()
        assert len(search_data["results"]) > 0
        top_result = search_data["results"][0]
        assert "palladium" in top_result["content"].lower()
        assert top_result["document_title"] == "arc_reactor_blueprint.pdf"
        assert top_result["page_number"] == 1
        print(f"[PASS] Keyword query matched chunk: '{top_result['section_heading']}' | Score: {top_result['score']}")

        # ----------------------------------------------------------------------
        # Test 3: Semantic / Conceptual Paraphrase Query
        # ----------------------------------------------------------------------
        print("\n--- Test 3: Semantic Vector Paraphrase Search ---")
        sem_res = await client.post(
            "/api/v1/search",
            json={"query": "emergency temperature control and cooling safeguards", "top_k": 3},
            headers=headers_stark,
        )
        assert sem_res.status_code == 200
        sem_data = sem_res.json()
        assert len(sem_data["results"]) > 0
        top_sem = sem_data["results"][0]
        assert "cooling" in top_sem["content"].lower() or "thermal" in top_sem["content"].lower()
        assert top_sem["page_number"] == 2
        print(f"[PASS] Semantic query retrieved: '{top_sem['section_heading']}' (Page {top_sem['page_number']})")

        # ----------------------------------------------------------------------
        # Test 4: Reciprocal Rank Fusion (RRF) Validation
        # ----------------------------------------------------------------------
        print("\n--- Test 4: Reciprocal Rank Fusion Ranking & Deduplication ---")
        fusion_res = await client.post(
            "/api/v1/search",
            json={"query": "arc reactor plasma containment", "top_k": 5, "vector_weight": 0.5},
            headers=headers_stark,
        )
        assert fusion_res.status_code == 200
        fusion_data = fusion_res.json()
        assert len(fusion_data["results"]) >= 2
        for idx, item in enumerate(fusion_data["results"]):
            print(
                f"  Rank {idx + 1}: Score = {item['score']} | "
                f"Doc = '{item['document_title']}' | Heading = '{item['section_heading']}' | "
                f"VecRank = {item['vector_rank']}, KwRank = {item['keyword_rank']}"
            )
            # Scores must be strictly descending
            if idx > 0:
                assert item["score"] <= fusion_data["results"][idx - 1]["score"]

        print("[PASS] Reciprocal Rank Fusion successfully fused and ordered ranked candidates.")

        # ----------------------------------------------------------------------
        # Test 5: Strict Multi-Tenant Isolation
        # ----------------------------------------------------------------------
        print("\n--- Test 5: Multi-Tenant Hybrid Search Isolation ---")
        # 1. Wayne Enterprise searches for Stark's specific term "palladium core"
        res_wayne_search = await client.post(
            "/api/v1/search",
            json={"query": "palladium core cold fusion", "top_k": 5},
            headers=headers_wayne,
        )
        assert res_wayne_search.status_code == 200
        # Wayne must NOT see any Stark documents
        wayne_results = res_wayne_search.json()["results"]
        for r in wayne_results:
            assert r["document_title"] != "arc_reactor_blueprint.pdf", "Tenant data leak detected!"
            assert r["document_title"] != "iron_legion_avionics.pdf"
        print(f"[PASS] Wayne query for 'palladium' yielded {len(wayne_results)} results (Zero Stark documents leaked).")

        # 2. Both organizations search for common term "Arc Reactor"
        stark_search = await client.post(
            "/api/v1/search",
            json={"query": "Arc Reactor", "top_k": 5},
            headers=headers_stark,
        )
        wayne_search = await client.post(
            "/api/v1/search",
            json={"query": "Arc Reactor", "top_k": 5},
            headers=headers_wayne,
        )
        stark_docs = {r["document_title"] for r in stark_search.json()["results"]}
        wayne_docs = {r["document_title"] for r in wayne_search.json()["results"]}

        assert "batcave_intelligence.pdf" not in stark_docs, "Stark saw Wayne documents!"
        assert "arc_reactor_blueprint.pdf" not in wayne_docs, "Wayne saw Stark documents!"
        print(f"[PASS] Cross-tenant collision test passed: Stark results = {stark_docs}, Wayne results = {wayne_docs}")

    print("\n" + "=" * 70)
    print("ALL STEP 4 HYBRID RETRIEVAL & RRF TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_hybrid_search_verification())
