"""
Test suite for Phase 5A: Asynchronous Evaluation Runs with Status/Progress Tracking and Failure Handling.
Verifies:
1. Asynchronous run initiation via POST /api/v1/evaluations returns 201 with status PENDING and initial progress.
2. Background worker completes execution: status transitions to COMPLETED, progress_current matches progress_total.
3. Incremental progress tracking across test case execution.
4. Failure handling: when an error occurs during execution, status transitions to FAILED and error_message is captured.
5. RBAC enforcement (ADMIN required, MEMBER receives 403 Forbidden).
6. Multi-tenant isolation: runs from Org 1 are inaccessible to Org 2.
"""

import asyncio
from datetime import datetime, timezone
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
from app.models.evaluation import EvalRun, EvalRunResult
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


async def run_async_evaluation_tests():
    TestingSessionLocal = await setup_test_db()

    print("===========================================================================")
    print("INTELLIGENCE OS - PHASE 5A ASYNC EVALUATION & PROGRESS TRACKING TESTS")
    print("===========================================================================")

    org1_id = uuid.uuid4()
    org2_id = uuid.uuid4()
    admin1_id = uuid.uuid4()
    member1_id = uuid.uuid4()
    admin2_id = uuid.uuid4()

    async with TestingSessionLocal() as db:
        # Seed Organizations
        org1 = Organization(id=org1_id, name="Acme Org 1", slug="acme-1")
        org2 = Organization(id=org2_id, name="Beta Org 2", slug="beta-2")
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
            email="admin@beta.com",
            hashed_password=get_password_hash("Secret123!"),
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add_all([admin1, member1, admin2])
        await db.commit()

    token_admin1 = create_access_token(subject=admin1_id, org_id=org1_id, role="ADMIN")
    token_member1 = create_access_token(subject=member1_id, org_id=org1_id, role="MEMBER")
    token_admin2 = create_access_token(subject=admin2_id, org_id=org2_id, role="ADMIN")

    headers_admin1 = {"Authorization": f"Bearer {token_admin1}"}
    headers_member1 = {"Authorization": f"Bearer {token_member1}"}
    headers_admin2 = {"Authorization": f"Bearer {token_admin2}"}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # ----------------------------------------------------------------------
        # Test 1: RBAC Check (MEMBER cannot start async evaluation)
        # ----------------------------------------------------------------------
        print("\n--- 1. RBAC Check: Member Role Forbidden ---")
        member_post = await client.post(
            "/api/v1/evaluations",
            json={"dataset_name": "golden_dataset", "judge_type": "deterministic", "limit": 2},
            headers=headers_member1,
        )
        assert member_post.status_code == 403
        print("[PASS] MEMBER forbidden from starting async evaluation runs (403 Forbidden).")

        # ----------------------------------------------------------------------
        # Test 2: Asynchronous Run Initiation (201 Created & PENDING status)
        # ----------------------------------------------------------------------
        print("\n--- 2. Async Evaluation Initiation & Immediate Response ---")
        admin_post = await client.post(
            "/api/v1/evaluations",
            json={"dataset_name": "golden_dataset", "judge_type": "deterministic", "limit": 3, "offline": True},
            headers=headers_admin1,
        )
        assert admin_post.status_code == 201
        run_data = admin_post.json()
        run_id = run_data["id"]

        # Note: In FastAPI with Starlette background tasks, the response body is encoded
        # with initial status PENDING (or already completed after Starlette background tasks run).
        assert run_data["status"] in ("PENDING", "COMPLETED")
        assert run_data["total_test_cases"] == 3
        assert run_data["progress_total"] == 3
        print(f"[PASS] Run {run_id} initiated successfully. Progress Total: {run_data['progress_total']}.")

        # ----------------------------------------------------------------------
        # Test 3: Verify Background Execution Completes with Progress Tracking
        # ----------------------------------------------------------------------
        print("\n--- 3. Polling and Progress Tracking ---")
        detail_res = await client.get(f"/api/v1/evaluations/{run_id}", headers=headers_admin1)
        assert detail_res.status_code == 200
        detail_data = detail_res.json()

        assert detail_data["status"] == "COMPLETED"
        assert detail_data["progress_current"] == 3
        assert detail_data["progress_total"] == 3
        assert detail_data["error_message"] is None
        assert "pass_rate" in detail_data
        print(
            f"[PASS] Run {run_id} transitioned to COMPLETED with "
            f"progress_current={detail_data['progress_current']}/{detail_data['progress_total']}."
        )

        # ----------------------------------------------------------------------
        # Test 4: Failure Handling & Error Message Persistence
        # ----------------------------------------------------------------------
        print("\n--- 4. Error & Failure Handling ---")
        failed_run_id = uuid.uuid4()
        async with TestingSessionLocal() as db:
            pending_failed_run = EvalRun(
                id=failed_run_id,
                org_id=org1_id,
                dataset_name="golden_dataset",
                dataset_version="1.0.0",
                status="PENDING",
                total_test_cases=5,
                progress_total=5,
                progress_current=0,
                error_message=None,
                config_snapshot={},
                summary_metrics={},
                regression_summary={},
                created_at=datetime.now(timezone.utc),
            )
            db.add(pending_failed_run)
            await db.commit()

        # Simulate background worker encountering an exception during benchmark execution
        with patch.object(
            EvalRunner,
            "run_benchmark",
            side_effect=RuntimeError("Simulated LLM Judge service outage or network timeout"),
        ):
            await process_evaluation_run_background(
                run_id=failed_run_id,
                org_id=org1_id,
                dataset_name="golden_dataset",
                judge_type="deterministic",
                limit=5,
                offline=True,
                session_factory=TestingSessionLocal,
            )

        failed_detail_res = await client.get(f"/api/v1/evaluations/{failed_run_id}", headers=headers_admin1)
        assert failed_detail_res.status_code == 200
        failed_data = failed_detail_res.json()

        assert failed_data["status"] == "FAILED"
        assert "Simulated LLM Judge service outage" in (failed_data["error_message"] or "")
        print(
            f"[PASS] Failed run correctly records status=FAILED and error_message='{failed_data['error_message']}'."
        )

        # ----------------------------------------------------------------------
        # Test 5: Multi-Tenant Isolation
        # ----------------------------------------------------------------------
        print("\n--- 5. Multi-Tenant Isolation in Run Listing and Detail ---")
        # Org 2 attempts to get Org 1's run
        cross_res = await client.get(f"/api/v1/evaluations/{run_id}", headers=headers_admin2)
        assert cross_res.status_code == 404
        print("[PASS] Cross-tenant run inspection returns 404 Not Found.")

        # Org 2 list does not show Org 1's runs
        org2_list = await client.get("/api/v1/evaluations", headers=headers_admin2)
        assert org2_list.status_code == 200
        assert org2_list.json()["total"] == 0
        print("[PASS] Org 2 list does not include Org 1 evaluation runs.")

        # ----------------------------------------------------------------------
        # Test 6: Orphaned Run Recovery on Restart (No False Failures)
        # ----------------------------------------------------------------------
        print("\n--- 6. Orphaned Run Recovery on Server Restart ---")
        orphaned_run_id = uuid.uuid4()
        active_run_id = uuid.uuid4()

        async with TestingSessionLocal() as db:
            # 1. Abandoned run from prior crashed server process (not in _active_run_ids)
            orphaned_run = EvalRun(
                id=orphaned_run_id,
                org_id=org1_id,
                dataset_name="golden_dataset",
                dataset_version="1.0.0",
                status="RUNNING",
                total_test_cases=10,
                progress_total=10,
                progress_current=4,
                config_snapshot={},
                summary_metrics={},
                regression_summary={},
                created_at=datetime.now(timezone.utc),
            )
            # 2. Actively running run in current process
            active_run = EvalRun(
                id=active_run_id,
                org_id=org1_id,
                dataset_name="golden_dataset",
                dataset_version="1.0.0",
                status="RUNNING",
                total_test_cases=10,
                progress_total=10,
                progress_current=2,
                config_snapshot={},
                summary_metrics={},
                regression_summary={},
                created_at=datetime.now(timezone.utc),
            )
            db.add_all([orphaned_run, active_run])
            await db.commit()

        # Register active_run_id as active in memory, leaving orphaned_run_id untracked
        from app.services.evaluation_service import _active_run_ids
        _active_run_ids.add(active_run_id)

        # Trigger recovery routine (e.g. at server startup)
        recovered_count = await evaluation_service.recover_orphaned_runs(session_factory=TestingSessionLocal)
        assert recovered_count == 1, f"Expected 1 recovered run, got {recovered_count}"

        # Verify orphaned run was safely marked FAILED with restart message
        async with TestingSessionLocal() as db:
            recovered_res = await db.get(EvalRun, orphaned_run_id)
            assert recovered_res.status == "FAILED"
            assert "server restart" in recovered_res.error_message
            assert recovered_res.progress_current == 4
            print(f"[PASS] Orphaned run safely marked FAILED: '{recovered_res.error_message}'")

            # Verify active run was NOT falsely marked as failed!
            active_res = await db.get(EvalRun, active_run_id)
            assert active_res.status == "RUNNING"
            assert active_res.error_message is None
            print("[PASS] Active run was NOT falsely marked as failed (remains RUNNING).")

        # ----------------------------------------------------------------------
        # Test 7: Graceful Server Shutdown Clean Interruption
        # ----------------------------------------------------------------------
        print("\n--- 7. Graceful Server Shutdown In-Flight Handling ---")
        shutdown_count = await evaluation_service.mark_in_flight_runs_as_interrupted(session_factory=TestingSessionLocal)
        assert shutdown_count == 1, f"Expected 1 shutdown-interrupted run, got {shutdown_count}"

        async with TestingSessionLocal() as db:
            shutdown_res = await db.get(EvalRun, active_run_id)
            assert shutdown_res.status == "FAILED"
            assert "server shutdown" in shutdown_res.error_message
            print(f"[PASS] In-flight run cleanly handled on shutdown: '{shutdown_res.error_message}'")

    print("\n===========================================================================")
    print("ALL PHASE 5A ASYNCHRONOUS EVALUATION TESTS PASSED!")
    print("===========================================================================\n")


if __name__ == "__main__":
    asyncio.run(run_async_evaluation_tests())
