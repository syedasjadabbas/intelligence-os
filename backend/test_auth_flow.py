"""
Verification script for Step 2:
Tests Multi-Tenant Organization Registration, Admin Login, Role-Based Access Control,
and Tenant Isolation using FastAPI TestClient with httpx and an isolated AsyncSession.
"""

import asyncio
import sys
import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.main import app
from app.models import Base


async def run_verification():
    print("=" * 70)
    print("INTELLIGENCE OS - STEP 2 VERIFICATION SUITE")
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

    # Create all tables including organizations, users, documents, chunks, conversations, messages
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[PASS] Test database initialized and schema created.")

    # Override database dependency for app
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
        # Test 1: Organization Registration (Creates Admin User)
        # ----------------------------------------------------------------------
        print("\n--- Test 1: Register New Organization & Admin User ---")
        reg_payload = {
            "org_name": "Nexus Defense",
            "org_slug": "nexus-defense",
            "admin_email": "chief@nexusdefense.com",
            "admin_password": "SecurePassword123!",
        }
        res = await client.post("/api/v1/auth/register-org", json=reg_payload)
        assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
        reg_data = res.json()
        assert "access_token" in reg_data, "Response missing access_token"
        assert reg_data["user"]["role"] == "ADMIN", "User role must be ADMIN"
        assert reg_data["user"]["email"] == "chief@nexusdefense.com"
        assert reg_data["organization"]["slug"] == "nexus-defense"
        admin_token = reg_data["access_token"]
        org_id = reg_data["organization"]["id"]
        print(f"[PASS] Organization '{reg_data['organization']['name']}' created (ID: {org_id})")
        print(f"[PASS] Admin user created with role '{reg_data['user']['role']}'")

        # ----------------------------------------------------------------------
        # Test 2: Admin Login
        # ----------------------------------------------------------------------
        print("\n--- Test 2: Login via JSON Credentials ---")
        login_payload = {
            "email": "chief@nexusdefense.com",
            "password": "SecurePassword123!",
        }
        res = await client.post("/api/v1/auth/login", json=login_payload)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        login_data = res.json()
        assert "access_token" in login_data
        print("[PASS] Admin logged in successfully and received JWT token.")

        # ----------------------------------------------------------------------
        # Test 3: Authenticated User Profile (/auth/me)
        # ----------------------------------------------------------------------
        print("\n--- Test 3: Fetch Profile via /auth/me ---")
        headers_admin = {"Authorization": f"Bearer {admin_token}"}
        res = await client.get("/api/v1/auth/me", headers=headers_admin)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        profile = res.json()
        assert profile["email"] == "chief@nexusdefense.com"
        assert profile["role"] == "ADMIN"
        assert profile["organization"]["slug"] == "nexus-defense"
        print(f"[PASS] /auth/me verified: {profile['email']} | Org: {profile['organization']['name']}")

        # ----------------------------------------------------------------------
        # Test 4: Admin Creates a Member User
        # ----------------------------------------------------------------------
        print("\n--- Test 4: Admin Invites/Creates Member in Organization ---")
        new_member_payload = {
            "email": "analyst@nexusdefense.com",
            "password": "AnalystPassword456!",
            "role": "MEMBER",
        }
        res = await client.post(
            "/api/v1/org/users",
            json=new_member_payload,
            headers=headers_admin,
        )
        assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
        member_data = res.json()
        assert member_data["email"] == "analyst@nexusdefense.com"
        assert member_data["role"] == "MEMBER"
        assert member_data["org_id"] == org_id, "Member must share the same org_id"
        print(f"[PASS] Member created under Org {org_id}: {member_data['email']}")

        # ----------------------------------------------------------------------
        # Test 5: Member Login & RBAC Verification (Member Cannot Create Users)
        # ----------------------------------------------------------------------
        print("\n--- Test 5: Member Login & RBAC Enforcement (403 Forbidden) ---")
        res = await client.post(
            "/api/v1/auth/login",
            json={"email": "analyst@nexusdefense.com", "password": "AnalystPassword456!"},
        )
        assert res.status_code == 200
        member_token = res.json()["access_token"]
        headers_member = {"Authorization": f"Bearer {member_token}"}

        # Attempt to create another user as MEMBER
        unauthorized_res = await client.post(
            "/api/v1/org/users",
            json={"email": "hacker@nexusdefense.com", "password": "Pass!", "role": "ADMIN"},
            headers=headers_member,
        )
        assert unauthorized_res.status_code == 403, f"Expected 403 Forbidden, got {unauthorized_res.status_code}"
        print(f"[PASS] Non-admin access rejected with 403 Forbidden: {unauthorized_res.json()['detail']}")

        # ----------------------------------------------------------------------
        # Test 6: List Organization Users (Tenant Scoped)
        # ----------------------------------------------------------------------
        print("\n--- Test 6: List Organization Users ---")
        res = await client.get("/api/v1/org/users", headers=headers_member)
        assert res.status_code == 200
        users_list = res.json()
        assert len(users_list) == 2, f"Expected 2 users, got {len(users_list)}"
        emails = [u["email"] for u in users_list]
        assert "chief@nexusdefense.com" in emails
        assert "analyst@nexusdefense.com" in emails
        print(f"[PASS] Organization users listed ({len(users_list)} total): {emails}")

        # ----------------------------------------------------------------------
        # Test 7: Multi-Tenant Isolation (Register Second Org & Verify Isolation)
        # ----------------------------------------------------------------------
        print("\n--- Test 7: Multi-Tenant Data Isolation ---")
        res_org2 = await client.post(
            "/api/v1/auth/register-org",
            json={
                "org_name": "Apex AI",
                "org_slug": "apex-ai",
                "admin_email": "admin@apexai.io",
                "admin_password": "ApexPassword789!",
            },
        )
        assert res_org2.status_code == 201
        org2_token = res_org2.json()["access_token"]
        headers_org2 = {"Authorization": f"Bearer {org2_token}"}

        # Org 2 users list must ONLY contain Org 2 users
        res_org2_users = await client.get("/api/v1/org/users", headers=headers_org2)
        assert res_org2_users.status_code == 200
        org2_users = res_org2_users.json()
        assert len(org2_users) == 1
        assert org2_users[0]["email"] == "admin@apexai.io"
        assert "chief@nexusdefense.com" not in [u["email"] for u in org2_users]
        print(f"[PASS] Tenant isolation verified: Org 2 cannot see Org 1 users!")

    print("\n" + "=" * 70)
    print("ALL STEP 2 VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_verification())
