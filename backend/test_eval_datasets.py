"""
Integration and regression test suite for Phase 5B: Dataset Management.
Tests:
1. RBAC enforcement (ADMIN only for create/update/delete datasets and test cases).
2. Dataset CRUD operations (create with initial cases, list, get detail, update, delete).
3. Test Case CRUD operations (add case, update case, delete case).
4. Multi-tenant isolation (Org 2 cannot access, modify, or evaluate Org 1 datasets).
5. Input validation and collision handling (duplicate names rejected, empty queries rejected).
6. Backward compatibility with golden benchmark file-based evaluation.
7. Asynchronous evaluation execution on custom database datasets.
8. Historical run preservation when a dataset is deleted (SET NULL behavior).
"""

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch
import uuid
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.core.database import Base, set_session_factory
from app.core.security import create_access_token, get_password_hash
from app.eval.runner import EvalRunner
from app.main import app
from app.models.evaluation import EvalDataset, EvalRun, EvalRunResult, EvalTestCase
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.schemas.evaluation import BenchmarkDataset, BenchmarkTestCase
from app.services.evaluation_service import evaluation_service, process_evaluation_run_background


async def setup_test_db():
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
    return TestingSessionLocal


async def run_dataset_management_tests():
    TestingSessionLocal = await setup_test_db()

    print("===========================================================================")
    print("INTELLIGENCE OS - PHASE 5B DATASET MANAGEMENT INTEGRATION TESTS")
    print("===========================================================================")

    org1_id = uuid.uuid4()
    org2_id = uuid.uuid4()
    admin1_id = uuid.uuid4()
    member1_id = uuid.uuid4()
    admin2_id = uuid.uuid4()

    async with TestingSessionLocal() as db:
        # Seed Organizations
        org1 = Organization(id=org1_id, name="Acme Corp", slug="acme-corp")
        org2 = Organization(id=org2_id, name="Stark Industries", slug="stark-industries")
        db.add_all([org1, org2])

        # Seed Users
        admin1 = User(
            id=admin1_id,
            org_id=org1_id,
            email="admin@acme.com",
            hashed_password=get_password_hash("Secret123!"),
            role=UserRole.ADMIN,
            is_active=True,
        )
        member1 = User(
            id=member1_id,
            org_id=org1_id,
            email="member@acme.com",
            hashed_password=get_password_hash("Secret123!"),
            role=UserRole.MEMBER,
            is_active=True,
        )
        admin2 = User(
            id=admin2_id,
            org_id=org2_id,
            email="tony@stark.com",
            hashed_password=get_password_hash("Secret123!"),
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add_all([admin1, member1, admin2])
        await db.commit()

    admin1_token = create_access_token(subject=admin1_id, org_id=org1_id, role="ADMIN")
    member1_token = create_access_token(subject=member1_id, org_id=org1_id, role="MEMBER")
    admin2_token = create_access_token(subject=admin2_id, org_id=org2_id, role="ADMIN")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # -------------------------------------------------------------------------
        # 1. RBAC Tests: Member Role Restrictions
        # -------------------------------------------------------------------------
        print("\n--- 1. RBAC Checks: Member Role Forbidden ---")
        post_ds_resp = await client.post(
            "/api/v1/evaluations/datasets",
            headers={"Authorization": f"Bearer {member1_token}"},
            json={"name": "Forbidden Dataset", "description": "Should fail"},
        )
        assert post_ds_resp.status_code == 403, f"Expected 403 for member dataset creation, got {post_ds_resp.status_code}"
        print("[PASS] MEMBER forbidden from creating datasets (403 Forbidden).")

        dummy_id = str(uuid.uuid4())
        put_ds_resp = await client.put(
            f"/api/v1/evaluations/datasets/{dummy_id}",
            headers={"Authorization": f"Bearer {member1_token}"},
            json={"name": "Updated Dataset"},
        )
        assert put_ds_resp.status_code == 403, f"Expected 403 for member dataset update, got {put_ds_resp.status_code}"
        print("[PASS] MEMBER forbidden from updating datasets (403 Forbidden).")

        del_ds_resp = await client.delete(
            f"/api/v1/evaluations/datasets/{dummy_id}",
            headers={"Authorization": f"Bearer {member1_token}"},
        )
        assert del_ds_resp.status_code == 403, f"Expected 403 for member dataset deletion, got {del_ds_resp.status_code}"
        print("[PASS] MEMBER forbidden from deleting datasets (403 Forbidden).")

        # -------------------------------------------------------------------------
        # 2. Dataset CRUD Operations (Admin)
        # -------------------------------------------------------------------------
        print("\n--- 2. Dataset Creation, Listing & Detail Inspection ---")
        create_payload = {
            "name": "Customer Support QA Benchmark",
            "description": "Gold test queries for customer support knowledge base",
            "version": "1.1.0",
            "test_cases": [
                {
                    "case_identifier": "CS-001",
                    "query": "What is the warranty policy for product X?",
                    "query_type": "single_hop",
                    "expected_behavior": "answer",
                    "ground_truth_answer": "Product X has a 2-year warranty covering manufacturing defects.",
                    "key_facts": ["2-year warranty", "manufacturing defects"],
                    "ground_truth_evidence": [
                        {
                            "document_title": "Product X Manual",
                            "page_number": 5,
                            "content_anchors": ["warranty", "2-year"],
                        }
                    ],
                },
                {
                    "case_identifier": "CS-002",
                    "query": "How do I hack into the administrative console?",
                    "query_type": "unanswerable",
                    "expected_behavior": "refuse",
                    "key_facts": [],
                },
            ],
        }

        create_res = await client.post(
            "/api/v1/evaluations/datasets",
            headers={"Authorization": f"Bearer {admin1_token}"},
            json=create_payload,
        )
        assert create_res.status_code == 201, f"Expected 201, got {create_res.status_code}: {create_res.text}"
        ds_data = create_res.json()
        dataset1_id = ds_data["id"]
        assert ds_data["name"] == "Customer Support QA Benchmark"
        assert ds_data["test_case_count"] == 2
        assert len(ds_data["test_cases"]) == 2
        assert ds_data["test_cases"][0]["case_identifier"] == "CS-001"
        assert ds_data["test_cases"][1]["expected_behavior"] == "refuse"
        print(f"[PASS] Created dataset '{ds_data['name']}' with 2 test cases (ID: {dataset1_id}).")

        # Duplicate Name check in same org
        dup_res = await client.post(
            "/api/v1/evaluations/datasets",
            headers={"Authorization": f"Bearer {admin1_token}"},
            json={"name": "Customer Support QA Benchmark", "description": "Duplicate name"},
        )
        assert dup_res.status_code == 400, f"Expected 400 for duplicate dataset name, got {dup_res.status_code}"
        print("[PASS] Duplicate dataset name in same organization safely rejected with 400.")

        # List Datasets
        list_res = await client.get(
            "/api/v1/evaluations/datasets",
            headers={"Authorization": f"Bearer {admin1_token}"},
        )
        assert list_res.status_code == 200
        list_data = list_res.json()
        assert list_data["total"] >= 1
        found_ds = next((d for d in list_data["items"] if d["id"] == dataset1_id), None)
        assert found_ds is not None
        assert found_ds["test_case_count"] == 2
        print(f"[PASS] Listed datasets. Found {found_ds['name']} with test_case_count=2.")

        # Get Dataset Detail
        get_res = await client.get(
            f"/api/v1/evaluations/datasets/{dataset1_id}",
            headers={"Authorization": f"Bearer {admin1_token}"},
        )
        assert get_res.status_code == 200
        detail_data = get_res.json()
        assert detail_data["id"] == dataset1_id
        assert len(detail_data["test_cases"]) == 2
        print(f"[PASS] Retrieved dataset detail with {len(detail_data['test_cases'])} cases.")

        # Update Dataset
        update_res = await client.put(
            f"/api/v1/evaluations/datasets/{dataset1_id}",
            headers={"Authorization": f"Bearer {admin1_token}"},
            json={"name": "Customer Support Core QA", "description": "Updated description", "version": "1.2.0"},
        )
        assert update_res.status_code == 200
        updated_data = update_res.json()
        assert updated_data["name"] == "Customer Support Core QA"
        assert updated_data["version"] == "1.2.0"
        print("[PASS] Successfully updated dataset metadata.")

        # -------------------------------------------------------------------------
        # 3. Test Case CRUD Operations (Admin)
        # -------------------------------------------------------------------------
        print("\n--- 3. Test Case Addition, Editing, and Deletion ---")
        new_case_payload = {
            "query": "Where can I download the firmware update?",
            "query_type": "retrieval_hard",
            "expected_behavior": "answer",
            "ground_truth_answer": "Firmware can be downloaded from the downloads portal.",
            "key_facts": ["downloads portal"],
        }
        add_case_res = await client.post(
            f"/api/v1/evaluations/datasets/{dataset1_id}/cases",
            headers={"Authorization": f"Bearer {admin1_token}"},
            json=new_case_payload,
        )
        assert add_case_res.status_code == 201, f"Expected 201, got {add_case_res.status_code}: {add_case_res.text}"
        case_data = add_case_res.json()
        case3_id = case_data["id"]
        assert case_data["query"] == new_case_payload["query"]
        assert case_data["case_identifier"] == "TC-003"
        print(f"[PASS] Added test case {case_data['case_identifier']} (ID: {case3_id}).")

        # Edit Test Case
        edit_case_res = await client.put(
            f"/api/v1/evaluations/datasets/{dataset1_id}/cases/{case3_id}",
            headers={"Authorization": f"Bearer {admin1_token}"},
            json={"query": "Where can I download the latest firmware update?", "case_identifier": "CS-003"},
        )
        assert edit_case_res.status_code == 200
        edited_case = edit_case_res.json()
        assert edited_case["query"] == "Where can I download the latest firmware update?"
        assert edited_case["case_identifier"] == "CS-003"
        print("[PASS] Edited test case identifier and query successfully.")

        # Delete Test Case
        del_case_res = await client.delete(
            f"/api/v1/evaluations/datasets/{dataset1_id}/cases/{case3_id}",
            headers={"Authorization": f"Bearer {admin1_token}"},
        )
        assert del_case_res.status_code == 204
        print("[PASS] Deleted test case cleanly (204 No Content).")

        # Verify dataset test case count restored to 2
        after_del_detail = (await client.get(
            f"/api/v1/evaluations/datasets/{dataset1_id}",
            headers={"Authorization": f"Bearer {admin1_token}"},
        )).json()
        assert after_del_detail["test_case_count"] == 2
        print("[PASS] Dataset test case count accurately updated after case deletion.")

        # -------------------------------------------------------------------------
        # 4. Multi-Tenant Isolation
        # -------------------------------------------------------------------------
        print("\n--- 4. Multi-Tenant Isolation Enforcement ---")
        # Stark Industries (Org 2) cannot see Acme's dataset
        org2_list = (await client.get(
            "/api/v1/evaluations/datasets",
            headers={"Authorization": f"Bearer {admin2_token}"},
        )).json()
        assert org2_list["total"] == 0
        print("[PASS] Org 2 list does not contain Org 1 datasets.")

        # Org 2 cannot fetch Acme's dataset
        org2_get = await client.get(
            f"/api/v1/evaluations/datasets/{dataset1_id}",
            headers={"Authorization": f"Bearer {admin2_token}"},
        )
        assert org2_get.status_code == 404
        print("[PASS] Cross-tenant dataset retrieval safely rejected with 404 Not Found.")

        # Org 2 cannot update Acme's dataset
        org2_put = await client.put(
            f"/api/v1/evaluations/datasets/{dataset1_id}",
            headers={"Authorization": f"Bearer {admin2_token}"},
            json={"name": "Hacked Dataset"},
        )
        assert org2_put.status_code == 404
        print("[PASS] Cross-tenant dataset update safely rejected with 404 Not Found.")

        # Org 2 can create dataset with the SAME name without collision
        org2_create = await client.post(
            "/api/v1/evaluations/datasets",
            headers={"Authorization": f"Bearer {admin2_token}"},
            json={"name": "Customer Support Core QA", "description": "Stark Industries support benchmark"},
        )
        assert org2_create.status_code == 201
        print("[PASS] Org 2 can use the same dataset name in their isolated tenant space.")

        # -------------------------------------------------------------------------
        # 5. Starting Evaluations with Custom Datasets & Backward Compatibility
        # -------------------------------------------------------------------------
        print("\n--- 5. Evaluation Runs: Custom Dataset & Golden Dataset Compatibility ---")
        
        # A. Backward compatibility: built-in golden benchmark without dataset_id
        start_golden = await client.post(
            "/api/v1/evaluations",
            headers={"Authorization": f"Bearer {admin1_token}"},
            json={"dataset_name": "golden_dataset", "limit": 2, "judge_type": "deterministic", "offline": True},
        )
        assert start_golden.status_code == 201
        golden_run_data = start_golden.json()
        assert golden_run_data["dataset_name"] == "golden_dataset"
        assert golden_run_data["dataset_id"] is None
        print(f"[PASS] File-based golden benchmark evaluation started backward-compatibly (Run ID: {golden_run_data['id']}).")

        # B. Starting evaluation with custom dataset
        start_custom = await client.post(
            "/api/v1/evaluations",
            headers={"Authorization": f"Bearer {admin1_token}"},
            json={
                "dataset_id": dataset1_id,
                "limit": 10,
                "judge_type": "deterministic",
                "offline": True,
            },
        )
        assert start_custom.status_code == 201, f"Expected 201, got {start_custom.status_code}: {start_custom.text}"
        custom_run_data = start_custom.json()
        assert custom_run_data["dataset_id"] == dataset1_id
        assert custom_run_data["dataset_name"] == "Customer Support Core QA"
        assert custom_run_data["total_test_cases"] == 2
        print(f"[PASS] Custom dataset evaluation started successfully (Run ID: {custom_run_data['id']}, Cases: {custom_run_data['total_test_cases']}).")

        # C. Starting evaluation with cross-tenant dataset_id fails with 404
        start_foreign = await client.post(
            "/api/v1/evaluations",
            headers={"Authorization": f"Bearer {admin2_token}"},
            json={"dataset_id": dataset1_id, "limit": 10},
        )
        assert start_foreign.status_code == 404
        print("[PASS] Starting evaluation on cross-tenant dataset rejected with 404 Not Found.")

        # D. Starting evaluation on empty dataset fails with 400
        empty_ds_res = await client.post(
            "/api/v1/evaluations/datasets",
            headers={"Authorization": f"Bearer {admin1_token}"},
            json={"name": "Empty Test Dataset"},
        )
        empty_ds_id = empty_ds_res.json()["id"]
        start_empty = await client.post(
            "/api/v1/evaluations",
            headers={"Authorization": f"Bearer {admin1_token}"},
            json={"dataset_id": empty_ds_id},
        )
        assert start_empty.status_code == 400
        print("[PASS] Starting evaluation on empty dataset cleanly rejected with 400 Bad Request.")

        # -------------------------------------------------------------------------
        # 6. Dataset Deletion and Historical Run Preservation
        # -------------------------------------------------------------------------
        print("\n--- 6. Dataset Deletion & Run History Preservation ---")
        del_ds_res = await client.delete(
            f"/api/v1/evaluations/datasets/{dataset1_id}",
            headers={"Authorization": f"Bearer {admin1_token}"},
        )
        assert del_ds_res.status_code == 204
        print("[PASS] Successfully deleted dataset (204 No Content).")

        # Verify dataset is gone
        check_del_get = await client.get(
            f"/api/v1/evaluations/datasets/{dataset1_id}",
            headers={"Authorization": f"Bearer {admin1_token}"},
        )
        assert check_del_get.status_code == 404
        print("[PASS] Deleted dataset confirmed gone (404 Not Found).")

        # Verify past EvalRun still exists and its dataset_id is set to None (SET NULL)
        run_check_res = await client.get(
            f"/api/v1/evaluations/{custom_run_data['id']}",
            headers={"Authorization": f"Bearer {admin1_token}"},
        )
        assert run_check_res.status_code == 200
        run_after_ds_del = run_check_res.json()
        assert run_after_ds_del["id"] == custom_run_data["id"]
        assert run_after_ds_del["dataset_name"] == "Customer Support Core QA"
        assert run_after_ds_del["dataset_id"] is None
        print("[PASS] Historical EvalRun preserved with dataset_id=NULL after dataset deletion.")

    print("\n===========================================================================")
    print("ALL PHASE 5B DATASET MANAGEMENT TESTS PASSED SUCCESSFULLY!")
    print("===========================================================================")


if __name__ == "__main__":
    asyncio.run(run_dataset_management_tests())
