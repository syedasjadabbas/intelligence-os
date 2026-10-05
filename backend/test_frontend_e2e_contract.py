"""
Step 6 Verification Suite: Frontend & Backend End-to-End Contract Verification.
Validates:
1. Organization registration and Login flow.
2. Document PDF upload, background ingestion, and transition to COMPLETED.
3. Conversation creation and chat answering with verifiable [Source 1] citations.
4. Citation structure validation for the Citation Drawer (title, page, excerpt).
5. Safe refusal guardrail triggering on unanswerable questions.
"""

import asyncio
from io import BytesIO
import uuid
import httpx
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.core.config import settings
from app.core.database import Base, set_session_factory
from app.main import app


def build_sample_pdf(title: str, heading: str, text: str) -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(72, 750, heading)
    c.setFont("Helvetica", 10)
    c.drawString(72, 720, text)
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()


async def run_e2e_contract_verification():
    print("=" * 75)
    print("INTELLIGENCE OS - STEP 6 FRONTEND/BACKEND E2E CONTRACT VERIFICATION")
    print("=" * 75)

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
        # 1. Organization Registration
        print("\n--- 1. Register Organization & Admin User ---")
        reg_res = await client.post(
            "/api/v1/auth/register-org",
            json={
                "org_name": "Wayne Enterprises",
                "org_slug": "wayne-corp",
                "admin_email": "bruce@waynecorp.com",
                "admin_password": "DarkKnightBatman1!",
            },
        )
        assert reg_res.status_code == 201
        reg_data = reg_res.json()
        assert "access_token" in reg_data
        assert reg_data["organization"]["name"] == "Wayne Enterprises"
        print(f"[PASS] Organization registered: {reg_data['organization']['name']} (slug: {reg_data['organization']['slug']})")

        # 2. Login
        print("\n--- 2. Login via API ---")
        login_res = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "bruce@waynecorp.com",
                "password": "DarkKnightBatman1!",
            },
        )
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("[PASS] User login succeeded with JWT token generation.")

        # 3. Document Upload and Polling to COMPLETED
        print("\n--- 3. Upload Document & Status Verification ---")
        pdf_bytes = build_sample_pdf(
            title="Batmobile Specifications",
            heading="# ADVANCED PROPULSION AND THERMAL CAMOUFLAGE",
            text="The Batmobile is equipped with hybrid gas turbine propulsion and active thermal camouflage systems.",
        )
        upload_res = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("batmobile_specs.pdf", pdf_bytes, "application/pdf")},
            headers=headers,
        )
        assert upload_res.status_code == 202
        doc_id = upload_res.json()["id"]
        print(f"[PASS] Document uploaded (status={upload_res.json()['status']}): ID {doc_id}")

        # Poll document status
        doc_res = await client.get(f"/api/v1/documents/{doc_id}", headers=headers)
        assert doc_res.status_code == 200
        assert doc_res.json()["status"] == "COMPLETED"
        assert doc_res.json()["total_chunks"] >= 1
        print(f"[PASS] Document transitioned to COMPLETED with {doc_res.json()['total_chunks']} indexed chunks.")

        # 4. Create Conversation & Grounded Chat
        print("\n--- 4. Conversation Creation & Grounded Q&A ---")
        conv_res = await client.post(
            "/api/v1/chat/conversations",
            json={"title": "Batmobile Q&A"},
            headers=headers,
        )
        assert conv_res.status_code == 201
        conv_id = conv_res.json()["id"]

        q_answerable = "What propulsion system does the Batmobile use?"
        chat_res = await client.post(
            f"/api/v1/chat/conversations/{conv_id}/messages",
            json={"question": q_answerable},
            headers=headers,
        )
        assert chat_res.status_code == 200
        chat_data = chat_res.json()
        print(f"Question: {q_answerable}")
        print(f"Answer: {chat_data['answer']}")

        assert "gas turbine" in chat_data["answer"].lower()
        assert "[Source 1]" in chat_data["answer"]
        assert len(chat_data["citations"]) >= 1
        print("[PASS] Grounded answer generated with interactive [Source 1] citation.")

        # 5. Citation Drawer Data Contract Verification
        print("\n--- 5. Citation Drawer Data Contract Verification ---")
        citation = chat_data["citations"][0]
        print(f"Inspecting Citation: {citation}")
        assert citation["source_index"] == 1
        assert citation["document_title"] == "batmobile_specs.pdf"
        assert citation["page_number"] == 1
        assert "PROPULSION" in (citation["section_heading"] or "").upper()
        assert "gas turbine" in (citation["content_snippet"] or "").lower()
        print("[PASS] Citation Drawer data contract fully verified.")

        # 6. Unanswerable Question Refusal Guardrail
        print("\n--- 6. Unanswerable Question Refusal Guardrail ---")
        q_refusal = "What is the quantum speed of the Flash in Metropolis?"
        refusal_res = await client.post(
            f"/api/v1/chat/conversations/{conv_id}/messages",
            json={"question": q_refusal},
            headers=headers,
        )
        assert refusal_res.status_code == 200
        refusal_data = refusal_res.json()
        print(f"Question: {q_refusal}")
        print(f"Response: {refusal_data['answer']}")
        print(f"is_refusal flag: {refusal_data['trace_data']['is_refusal']}")

        assert refusal_data["answer"] == settings.INSUFFICIENT_EVIDENCE_PHRASE
        assert refusal_data["citations"] == []
        assert refusal_data["trace_data"]["is_refusal"] is True
        print("[PASS] Refusal guardrail triggered safely without hallucinations.")

    print("\n" + "=" * 75)
    print("ALL FRONTEND/BACKEND E2E CONTRACT CHECKS PASSED!")
    print("=" * 75)


if __name__ == "__main__":
    asyncio.run(run_e2e_contract_verification())
