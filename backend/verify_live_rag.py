import asyncio
import json
import sys
import httpx
from dotenv import load_dotenv

load_dotenv(".env")

from app.core.security import create_access_token

async def main():
    print("=" * 70)
    print("VERIFYING LIVE RAG ENDPOINT VIA UVICORN (PORT 8000)")
    print("=" * 70)

    # User & Org IDs from intelligence_os_dev.db
    user_id = "1798ffdeee3947549e07e24f6df84ffd"
    org_id = "1e12cf233bbe4d41b6ed61732b76e6ed"

    token = create_access_token(subject=user_id, org_id=org_id, role="admin")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    base_url = "http://127.0.0.1:8000"

    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        # Check health
        health_res = await client.get("/health")
        print(f"Health check status: {health_res.status_code}, response: {health_res.json()}")
        assert health_res.status_code == 200

        # Create conversation
        conv_res = await client.post(
            "/api/v1/chat/conversations",
            json={"title": "Lonetex Workforce Inquiry"},
            headers=headers,
        )
        print(f"Create conversation status: {conv_res.status_code}")
        assert conv_res.status_code == 201
        conv_data = conv_res.json()
        conv_id = conv_data["id"]
        print(f"Created Conversation ID: {conv_id}")

        # Send question
        question = "What is the total workforce of lonetex?"
        print(f"\nSending Question: '{question}'...")
        msg_res = await client.post(
            f"/api/v1/chat/conversations/{conv_id}/messages",
            json={"question": question},
            headers=headers,
        )
        print(f"Message endpoint status: {msg_res.status_code}")
        assert msg_res.status_code == 200
        msg_data = msg_res.json()

        print("\n--- Response Received from Gemini RAG ---")
        print("Answer:", msg_data["answer"])
        print("\nCitations:")
        for c in msg_data.get("citations", []):
            print(f"  - [{c.get('source_tag')}] Doc: {c.get('document_title')}, Page: {c.get('page_number')}")
            print(f"    Snippet: {c.get('content_snippet')[:100]}...")

        print("\nTrace Data:")
        trace = msg_data.get("trace_data", {})
        print("  - Latencies (ms):", trace.get("latency_ms"))
        print("  - Generation Latency (ms):", trace.get("generation_latency_ms"))
        print("  - Is Refusal:", trace.get("is_refusal"))

        # Assertions
        assert "[Source 1]" in msg_data["answer"], "Answer must contain [Source 1]"
        assert "35" in msg_data["answer"], "Answer must mention 35"
        assert len(msg_data["citations"]) >= 1, "Must have at least 1 citation"
        first_cite = msg_data["citations"][0]
        assert first_cite["source_tag"] == "[Source 1]"
        assert "Lonetex" in first_cite["document_title"]
        assert first_cite["page_number"] == 1
        assert trace["generation_latency_ms"] > 0, "Generation latency must be recorded"
        print("\n" + "=" * 70)
        print("[SUCCESS] Live Gemini RAG test passed completely!")
        print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())
