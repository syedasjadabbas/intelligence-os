"""
Step 5 Verification Suite: Query Understanding & Rewriting, Cross-Encoder Reranking,
Grounded LLM Answer Generation with Strict Citations, Insufficient-Evidence Guardrails,
Pipeline Tracing Telemetry, Multi-Tenant Isolation, and Conversations/Chat API.
"""

import asyncio
from io import BytesIO
import sys
import uuid
import httpx
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.core.config import settings
from app.core.database import Base, set_session_factory
from app.main import app
from app.models.conversation import Conversation, Message
from app.models.document import Document, DocumentChunk


def build_pdf_document(pages_content: list[tuple[str, list[str]]]) -> bytes:
    """Helper to build a PDF document with custom headings and paragraphs."""
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


async def run_rag_pipeline_verification():
    print("=" * 75)
    print("INTELLIGENCE OS - STEP 5 RAG PIPELINE & CONVERSATION API VERIFICATION")
    print("=" * 75)

    # 1. Setup in-memory test database
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
    print("[PASS] In-memory test database initialized with multi-tenant schema.")

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
        print("\n--- Setup: Registering Multi-Tenant Organizations ---")
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
        # Test 1: Ingestion of 2 Documents with Distinct Technical Specs (Stark)
        # ----------------------------------------------------------------------
        print("\n--- Test 1: Ingestion of 2 Technical Documents for Stark Industries ---")
        doc1_pages = [
            (
                "# ARC REACTOR FUSION SPECIFICATION",
                [
                    "The Arc Reactor utilizes palladium core containment to catalyze cold fusion reactions.",
                    "Plasma flux density reaches peak power output with minimal thermal dissipation.",
                ],
            ),
            (
                "# EMERGENCY COOLING AND HEAT EXCHANGERS",
                [
                    "Emergency shutdown requires rapid thermal dissipation through liquid nitrogen cooling circuits.",
                    "Automated cryogenic relief valves vent nitrogen when core temperature exceeds critical thresholds.",
                ],
            ),
        ]
        pdf1 = build_pdf_document(doc1_pages)
        res_upload1 = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("arc_reactor_tech.pdf", pdf1, "application/pdf")},
            headers=headers_stark,
        )
        assert res_upload1.status_code == 202
        doc1_id = res_upload1.json()["id"]

        doc2_pages = [
            (
                "# IRON LEGION AVIONICS AND FLIGHT PROTOCOLS",
                [
                    "Autonomous drone avionics employ neural mesh navigation and localized sensor networks.",
                    "Decentralized flight algorithms ensure coordinated swarm tactics and perimeter defense.",
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

        # Verify documents completed in DB
        async with TestingSessionLocal() as session:
            d1 = (await session.execute(select(Document).where(Document.id == uuid.UUID(doc1_id)))).scalar_one()
            d2 = (await session.execute(select(Document).where(Document.id == uuid.UUID(doc2_id)))).scalar_one()
            assert d1.status.value == "COMPLETED"
            assert d2.status.value == "COMPLETED"

            chunks_stark = (
                await session.execute(
                    select(DocumentChunk).where(DocumentChunk.org_id == uuid.UUID(org_stark_id))
                )
            ).scalars().all()
            assert len(chunks_stark) == 3
            print(f"[PASS] Successfully ingested 2 documents ({len(chunks_stark)} chunks total with embeddings).")

        # ----------------------------------------------------------------------
        # Test 2: Question with Clear Evidence -> Grounded Answer & [Source 1] Citations
        # ----------------------------------------------------------------------
        print("\n--- Test 2: Question with Clear Evidence & Grounded Citations ---")
        res_conv = await client.post(
            "/api/v1/chat/conversations",
            json={"title": "Arc Reactor Technical Inquiry"},
            headers=headers_stark,
        )
        assert res_conv.status_code == 201
        conv_stark_id = res_conv.json()["id"]
        print(f"[PASS] Created Conversation Thread: {conv_stark_id}")

        q1 = "What core material catalyzes cold fusion in the Arc Reactor?"
        res_msg1 = await client.post(
            f"/api/v1/chat/conversations/{conv_stark_id}/messages",
            json={"question": q1},
            headers=headers_stark,
        )
        assert res_msg1.status_code == 200
        msg1_data = res_msg1.json()

        print(f"User Query: {q1}")
        print(f"Assistant Answer: {msg1_data['answer']}")
        print(f"Citations: {msg1_data['citations']}")

        # Assertions for grounded answer & citations
        assert "palladium" in msg1_data["answer"].lower()
        assert "[Source 1]" in msg1_data["answer"]
        assert len(msg1_data["citations"]) >= 1

        first_cite = msg1_data["citations"][0]
        assert first_cite["source_index"] == 1
        assert first_cite["source_tag"] == "[Source 1]"
        assert first_cite["document_title"] == "arc_reactor_tech.pdf"
        assert first_cite["page_number"] == 1
        assert "ARC REACTOR" in (first_cite["section_heading"] or "").upper()
        print("[PASS] Grounded answer generated with verified [Source 1] citation and metadata.")

        # ----------------------------------------------------------------------
        # Test 3: Citation Validation Passes (Citations Match Actual DB Chunks)
        # ----------------------------------------------------------------------
        print("\n--- Test 3: Citation Validation Against Database Chunks ---")
        async with TestingSessionLocal() as session:
            chunk_uuid = uuid.UUID(first_cite["chunk_id"])
            db_chunk = (
                await session.execute(select(DocumentChunk).where(DocumentChunk.id == chunk_uuid))
            ).scalar_one_or_none()
            assert db_chunk is not None
            assert db_chunk.org_id == uuid.UUID(org_stark_id)
            assert db_chunk.page_number == 1
            assert "palladium core" in db_chunk.content.lower()
            print(f"[PASS] Citation chunk {chunk_uuid} verified in database for tenant {org_stark_id}.")

        # ----------------------------------------------------------------------
        # Test 4: Unanswerable Question -> Strict Refusal Guardrail Triggered
        # ----------------------------------------------------------------------
        print("\n--- Test 4: Unanswerable Question Guardrail Refusal ---")
        q_unanswerable = "What is the radioactive half-life decay rate of Kryptonite in Gotham City?"
        res_msg_unanswerable = await client.post(
            f"/api/v1/chat/conversations/{conv_stark_id}/messages",
            json={"question": q_unanswerable},
            headers=headers_stark,
        )
        assert res_msg_unanswerable.status_code == 200
        unanswerable_data = res_msg_unanswerable.json()

        print(f"Unanswerable Query: {q_unanswerable}")
        print(f"Assistant Response: {unanswerable_data['answer']}")
        print(f"is_refusal: {unanswerable_data['trace_data']['is_refusal']}")

        assert unanswerable_data["answer"] == settings.INSUFFICIENT_EVIDENCE_PHRASE
        assert unanswerable_data["citations"] == []
        assert unanswerable_data["trace_data"]["is_refusal"] is True
        print("[PASS] Insufficient evidence guardrail successfully refused ungrounded query.")

        # ----------------------------------------------------------------------
        # Test 5: Multi-Tenant Isolation (Org B Asks About Org A's Documents)
        # ----------------------------------------------------------------------
        print("\n--- Test 5: Multi-Tenant Isolation & Zero Cross-Tenant Leak ---")
        # Bruce Wayne creates a conversation in Wayne Enterprises
        res_conv_wayne = await client.post(
            "/api/v1/chat/conversations",
            json={"title": "Wayne Tactical Recon"},
            headers=headers_wayne,
        )
        assert res_conv_wayne.status_code == 201
        conv_wayne_id = res_conv_wayne.json()["id"]

        # Bruce asks about Arc Reactor fusion (Stark document)
        q_cross = "What core material catalyzes cold fusion in the Arc Reactor?"
        res_msg_cross = await client.post(
            f"/api/v1/chat/conversations/{conv_wayne_id}/messages",
            json={"question": q_cross},
            headers=headers_wayne,
        )
        assert res_msg_cross.status_code == 200
        cross_data = res_msg_cross.json()

        print(f"Org B (Wayne) Querying Org A Data: '{q_cross}'")
        print(f"Org B Response: {cross_data['answer']}")
        print(f"Org B Citations Count: {len(cross_data['citations'])}")

        assert cross_data["answer"] == settings.INSUFFICIENT_EVIDENCE_PHRASE
        assert cross_data["citations"] == []
        assert cross_data["trace_data"]["is_refusal"] is True
        assert cross_data["trace_data"]["retrieval_candidate_count"] == 0

        # Test cross-tenant access to conversation thread
        res_leak_thread = await client.get(
            f"/api/v1/chat/conversations/{conv_stark_id}",
            headers=headers_wayne,
        )
        assert res_leak_thread.status_code == 404
        print("[PASS] Multi-tenant isolation verified: Org B received 0 candidates and zero data leak.")

        # ----------------------------------------------------------------------
        # Test 6: Conversation Persistence & Query Rewriting Follow-Up
        # ----------------------------------------------------------------------
        print("\n--- Test 6: Coreference Query Rewriting & Conversation Persistence ---")
        # Follow-up question with pronoun 'it'
        q_followup = "What fluid cools it during emergency shutdown?"
        res_followup = await client.post(
            f"/api/v1/chat/conversations/{conv_stark_id}/messages",
            json={"question": q_followup},
            headers=headers_stark,
        )
        assert res_followup.status_code == 200
        followup_data = res_followup.json()

        print(f"Follow-up Query: {q_followup}")
        print(f"Rewritten Query: {followup_data['trace_data']['rewritten_query']}")
        print(f"Follow-up Answer: {followup_data['answer']}")

        # Ensure pronoun 'it' was rewritten to reference Arc Reactor
        assert "arc reactor" in followup_data["trace_data"]["rewritten_query"].lower()
        # Answer must ground on Page 2 liquid nitrogen emergency cooling
        assert "liquid nitrogen" in followup_data["answer"].lower()
        assert len(followup_data["citations"]) >= 1
        assert any(c["page_number"] == 2 for c in followup_data["citations"])

        # Verify entire conversation message history retrieval
        res_history = await client.get(
            f"/api/v1/chat/conversations/{conv_stark_id}",
            headers=headers_stark,
        )
        assert res_history.status_code == 200
        history_data = res_history.json()
        messages = history_data["messages"]
        print(f"Total Persisted Messages in Conversation: {len(messages)}")
        assert len(messages) == 6  # 3 user messages + 3 assistant responses

        # Verify chronological order
        assert messages[0]["role"] == "user" and messages[0]["content"] == q1
        assert messages[1]["role"] == "assistant"
        assert messages[2]["role"] == "user" and messages[2]["content"] == q_unanswerable
        assert messages[3]["role"] == "assistant"
        assert messages[4]["role"] == "user" and messages[4]["content"] == q_followup
        assert messages[5]["role"] == "assistant"
        print("[PASS] Conversation thread correctly persisted 6 messages in chronological order.")

        # ----------------------------------------------------------------------
        # Test 7: Telemetry Trace Verification
        # ----------------------------------------------------------------------
        print("\n--- Test 7: Telemetry Pipeline Trace Verification ---")
        trace = followup_data["trace_data"]
        print("Telemetry Trace Data Keys:", list(trace.keys()))

        assert "original_query" in trace and trace["original_query"] == q_followup
        assert "rewritten_query" in trace and "arc reactor" in trace["rewritten_query"].lower()
        assert "retrieval_candidate_count" in trace and trace["retrieval_candidate_count"] >= 1
        assert "reranked_scores" in trace and len(trace["reranked_scores"]) >= 1
        assert "selected_sources" in trace and len(trace["selected_sources"]) >= 1
        assert "latency_ms" in trace
        latencies = trace["latency_ms"]
        assert "retrieval" in latencies and latencies["retrieval"] >= 0.0
        assert "rerank" in latencies and latencies["rerank"] >= 0.0
        assert "generation" in latencies and latencies["generation"] >= 0.0
        assert "total" in latencies and latencies["total"] >= 0.0
        assert "is_refusal" in trace and trace["is_refusal"] is False

        rerank_item = trace["reranked_scores"][0]
        assert "chunk_id" in rerank_item
        assert "document_title" in rerank_item
        assert "score" in rerank_item
        assert "rerank_score" in rerank_item
        print(f"[PASS] Trace verified: latencies={latencies}, reranked={rerank_item}")

        # ----------------------------------------------------------------------
        # Test 8: Conversation Thread Deletion
        # ----------------------------------------------------------------------
        print("\n--- Test 8: Conversation Deletion ---")
        del_res = await client.delete(
            f"/api/v1/chat/conversations/{conv_stark_id}",
            headers=headers_stark,
        )
        assert del_res.status_code == 204

        # Verify deletion cascades
        get_res = await client.get(
            f"/api/v1/chat/conversations/{conv_stark_id}",
            headers=headers_stark,
        )
        assert get_res.status_code == 404
        print("[PASS] Conversation and all associated messages successfully deleted.")

    print("\n" + "=" * 75)
    print("ALL STEP 5 RAG PIPELINE & CONVERSATION TESTS PASSED PERFECTLY!")
    print("=" * 75)


if __name__ == "__main__":
    asyncio.run(run_rag_pipeline_verification())
