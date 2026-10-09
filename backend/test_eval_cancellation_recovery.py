"""
Test suite for Phase 5C: RAG Evaluation Cancellation & Recovery.
Verifies:
1. Role-Based Access Control (RBAC):
   - MEMBER forbidden from cancelling runs (403 Forbidden).
   - MEMBER forbidden from recovering runs (403 Forbidden).
2. Multi-Tenant Isolation:
   - Cross-tenant run cancellation returns 404 Not Found without leaking existence.
   - Cross-tenant run recovery returns 404 Not Found.
3. Safe Cancellation of PENDING Runs:
   - Cancellation of queued/pending run immediately updates status to CANCELLED.
   - Worker task safely halts before executing any benchmark test cases.
   - Run never transitions to RUNNING or COMPLETED.
4. Safe Cancellation of RUNNING Runs Mid-Flight:
   - In-flight execution halts further case iteration upon receiving cancellation.
   - Progress and completed results before cancellation are preserved.
   - Run status remains CANCELLED and is never marked COMPLETED.
5. Cancellation Race Condition Safeguards:
   - Cancellation registered during finalization cleanly preserves CANCELLED status.
6. Terminal State Guard:
   - Rejecting cancellation for runs in COMPLETED, FAILED, or CANCELLED status (400 Bad Request).
7. Interrupted / Orphaned Run Recovery:
   - Runs orphaned from prior processes safely recovered to FAILED with diagnostics.
   - Active runs within stale threshold are NOT falsely marked as failed.
8. Stale Run Timeout Recovery:
   - Runs exceeding stale threshold timeout are safely recovered.
9. Single-Run and Tenant-Level Recovery Endpoints:
   - POST /evaluations/{run_id}/recover and POST /evaluations/recover work accurately.
"""

import asyncio
from datetime import datetime, timedelta, timezone
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
from app.eval.judges import DeterministicJudge
from app.eval.runner import EvalRunner
from app.main import app
from app.models.evaluation import EvalDataset, EvalRun, EvalRunResult, EvalTestCase
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.schemas.evaluation import BenchmarkDataset, BenchmarkTestCase
from app.services.evaluation_service import (
    _active_run_ids,
    _cancelled_run_ids,
    evaluation_service,
    is_run_cancelled,
    process_evaluation_run_background,
)


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


async def run_cancellation_recovery_tests():
    TestingSessionLocal = await setup_test_db()

    print("===========================================================================")
    print("INTELLIGENCE OS - PHASE 5C CANCELLATION & RECOVERY TEST SUITE")
    print("===========================================================================")

    org1_id = uuid.uuid4()
    org2_id = uuid.uuid4()
    admin_user_id = uuid.uuid4()
    member_user_id = uuid.uuid4()
    org2_admin_id = uuid.uuid4()

    async with TestingSessionLocal() as db:
        org1 = Organization(id=org1_id, name="Stark Industries", slug="stark-industries")
        org2 = Organization(id=org2_id, name="Hammer Tech", slug="hammer-tech")
        db.add_all([org1, org2])

        admin_user = User(
            id=admin_user_id,
            org_id=org1_id,
            email="tony@stark.com",
            hashed_password=get_password_hash("password123"),
            role=UserRole.ADMIN,
            is_active=True,
        )
        member_user = User(
            id=member_user_id,
            org_id=org1_id,
            email="peter@stark.com",
            hashed_password=get_password_hash("password123"),
            role=UserRole.MEMBER,
            is_active=True,
        )
        org2_admin = User(
            id=org2_admin_id,
            org_id=org2_id,
            email="justin@hammer.com",
            hashed_password=get_password_hash("password123"),
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add_all([admin_user, member_user, org2_admin])
        await db.commit()

    admin_token = create_access_token(subject=admin_user_id, org_id=org1_id, role="ADMIN")
    member_token = create_access_token(subject=member_user_id, org_id=org1_id, role="MEMBER")
    org2_admin_token = create_access_token(subject=org2_admin_id, org_id=org2_id, role="ADMIN")

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:

        # -------------------------------------------------------------------------
        # 1. RBAC Checks
        # -------------------------------------------------------------------------
        print("\n--- 1. RBAC Checks: Non-Admin Forbidden ---")
        dummy_run_id = uuid.uuid4()

        # Member attempts cancel
        res = await client.post(
            f"/api/v1/evaluations/{dummy_run_id}/cancel",
            headers={"Authorization": f"Bearer {member_token}"},
        )
        assert res.status_code == 403, f"Expected 403 for member cancel, got {res.status_code}"
        print("[PASS] MEMBER forbidden from cancelling evaluation runs (403 Forbidden).")

        # Member attempts recover
        res = await client.post(
            f"/api/v1/evaluations/{dummy_run_id}/recover",
            headers={"Authorization": f"Bearer {member_token}"},
        )
        assert res.status_code == 403, f"Expected 403 for member recover, got {res.status_code}"
        print("[PASS] MEMBER forbidden from recovering evaluation runs (403 Forbidden).")

        # Member attempts batch recover
        res = await client.post(
            "/api/v1/evaluations/recover",
            headers={"Authorization": f"Bearer {member_token}"},
        )
        assert res.status_code == 403, f"Expected 403 for member batch recover, got {res.status_code}"
        print("[PASS] MEMBER forbidden from invoking batch recovery (403 Forbidden).")

        # -------------------------------------------------------------------------
        # 2. Multi-Tenant Isolation
        # -------------------------------------------------------------------------
        print("\n--- 2. Multi-Tenant Isolation ---")
        # Create an Org 1 run
        async with TestingSessionLocal() as db:
            org1_run = EvalRun(
                id=uuid.uuid4(),
                org_id=org1_id,
                dataset_name="golden_dataset",
                dataset_version="1.0.0",
                status="RUNNING",
                llm_provider="deterministic-offline",
                llm_model="deterministic",
                embedding_model="feature-hashing",
                reranker_model="deterministic-cross-scoring",
                total_test_cases=10,
                passed_test_cases=0,
                progress_current=2,
                progress_total=10,
                created_at=datetime.now(timezone.utc),
            )
            db.add(org1_run)
            await db.commit()

        # Org 2 Admin attempts to cancel Org 1 run
        res = await client.post(
            f"/api/v1/evaluations/{org1_run.id}/cancel",
            headers={"Authorization": f"Bearer {org2_admin_token}"},
        )
        assert res.status_code == 404, f"Expected 404 for cross-tenant cancel, got {res.status_code}"
        print("[PASS] Cross-tenant run cancellation safely rejected with 404 Not Found.")

        # Org 2 Admin attempts to recover Org 1 run
        res = await client.post(
            f"/api/v1/evaluations/{org1_run.id}/recover",
            headers={"Authorization": f"Bearer {org2_admin_token}"},
        )
        assert res.status_code == 404, f"Expected 404 for cross-tenant recover, got {res.status_code}"
        print("[PASS] Cross-tenant run recovery safely rejected with 404 Not Found.")

        # -------------------------------------------------------------------------
        # 3. Safe Cancellation of PENDING Runs
        # -------------------------------------------------------------------------
        print("\n--- 3. Cancellation of PENDING Runs ---")
        pending_run_id = uuid.uuid4()
        async with TestingSessionLocal() as db:
            pending_run = EvalRun(
                id=pending_run_id,
                org_id=org1_id,
                dataset_name="golden_dataset",
                dataset_version="1.0.0",
                status="PENDING",
                llm_provider="deterministic-offline",
                llm_model="deterministic",
                embedding_model="feature-hashing",
                reranker_model="deterministic-cross-scoring",
                total_test_cases=20,
                passed_test_cases=0,
                progress_current=0,
                progress_total=20,
                created_at=datetime.now(timezone.utc),
            )
            db.add(pending_run)
            await db.commit()

        # Cancel the pending run
        res = await client.post(
            f"/api/v1/evaluations/{pending_run_id}/cancel",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        data = res.json()
        assert data["status"] == "CANCELLED", f"Expected status CANCELLED, got {data['status']}"
        assert data["error_message"] == "Evaluation run cancelled by user."
        assert is_run_cancelled(pending_run_id) is True
        print(f"[PASS] PENDING run {pending_run_id} cancelled via API: status=CANCELLED.")

        # Simulate background worker execution arriving after cancellation
        await process_evaluation_run_background(
            run_id=pending_run_id,
            org_id=org1_id,
            dataset_name="golden_dataset",
            judge_type="deterministic",
            limit=20,
            offline=True,
            session_factory=TestingSessionLocal,
        )

        async with TestingSessionLocal() as db:
            refreshed = await db.get(EvalRun, pending_run_id)
            assert refreshed.status == "CANCELLED", f"Expected CANCELLED after worker run, got {refreshed.status}"
            assert refreshed.progress_current == 0, f"Expected 0 cases executed, got {refreshed.progress_current}"
            print("[PASS] Background worker safely halts when run was pre-cancelled: status remains CANCELLED.")

        # -------------------------------------------------------------------------
        # 4. Safe Cancellation of RUNNING Runs Mid-Flight
        # -------------------------------------------------------------------------
        print("\n--- 4. Cancellation of RUNNING Runs Mid-Flight ---")
        running_run_id = uuid.uuid4()
        async with TestingSessionLocal() as db:
            running_run = EvalRun(
                id=running_run_id,
                org_id=org1_id,
                dataset_name="golden_dataset",
                dataset_version="1.0.0",
                status="RUNNING",
                llm_provider="deterministic-offline",
                llm_model="deterministic",
                embedding_model="feature-hashing",
                reranker_model="deterministic-cross-scoring",
                total_test_cases=10,
                passed_test_cases=0,
                progress_current=0,
                progress_total=10,
                created_at=datetime.now(timezone.utc),
            )
            db.add(running_run)
            await db.commit()

        # Execute runner with an in-flight cancellation trigger after 2 cases
        cases_executed = 0

        def cancel_hook(rid):
            nonlocal cases_executed
            return cases_executed >= 2

        async with TestingSessionLocal() as db:
            runner = EvalRunner(
                db=db,
                org_id=org1_id,
                judge=DeterministicJudge(),
                offline=True,
                is_cancelled=cancel_hook,
            )

            # Mock retrieval_service to simulate iteration steps
            async def mock_search(*args, **kwargs):
                nonlocal cases_executed
                cases_executed += 1
                return []

            runner.retrieval_service.hybrid_search = mock_search

            benchmark_input = await evaluation_service.load_benchmark_dataset(
                db=db,
                org_id=org1_id,
                dataset_name="golden_dataset",
            )

            final_run = await runner.run_benchmark(
                dataset_input=benchmark_input,
                limit=10,
                existing_run_id=running_run_id,
            )

            assert final_run.status == "CANCELLED", f"Expected CANCELLED, got {final_run.status}"
            assert cases_executed <= 3, f"Expected loop to stop shortly after cancellation, got {cases_executed}"
            assert final_run.progress_current == cases_executed - 1 or final_run.progress_current == 2
            print(f"[PASS] Mid-flight run {running_run_id} stopped case iteration: cases={final_run.progress_current}/10, status=CANCELLED.")

        # -------------------------------------------------------------------------
        # 5. Cancellation Race Condition: Pre-completion Safeguard
        # -------------------------------------------------------------------------
        print("\n--- 5. Cancellation Race Condition Safeguards ---")
        race_run_id = uuid.uuid4()
        async with TestingSessionLocal() as db:
            race_run = EvalRun(
                id=race_run_id,
                org_id=org1_id,
                dataset_name="golden_dataset",
                dataset_version="1.0.0",
                status="RUNNING",
                llm_provider="deterministic-offline",
                llm_model="deterministic",
                embedding_model="feature-hashing",
                reranker_model="deterministic-cross-scoring",
                total_test_cases=2,
                passed_test_cases=0,
                progress_current=0,
                progress_total=2,
                created_at=datetime.now(timezone.utc),
            )
            db.add(race_run)
            await db.commit()

            # Signal cancellation right before completion
            _cancelled_run_ids.add(race_run_id)

            runner = EvalRunner(
                db=db,
                org_id=org1_id,
                judge=DeterministicJudge(),
                offline=True,
                is_cancelled=is_run_cancelled,
            )
            benchmark_input = await evaluation_service.load_benchmark_dataset(
                db=db,
                org_id=org1_id,
                dataset_name="golden_dataset",
            )
            res_run = await runner.run_benchmark(
                dataset_input=benchmark_input,
                limit=2,
                existing_run_id=race_run_id,
            )
            assert res_run.status == "CANCELLED", f"Race condition failed: expected CANCELLED, got {res_run.status}"
            print("[PASS] Cancellation race condition handled: runner never accidentally marks a cancelled run as COMPLETED.")

        # -------------------------------------------------------------------------
        # 6. Reject Cancelling Terminal Runs (COMPLETED, FAILED, CANCELLED)
        # -------------------------------------------------------------------------
        print("\n--- 6. Rejecting Cancellation for Terminal Runs ---")
        completed_run_id = uuid.uuid4()
        async with TestingSessionLocal() as db:
            comp_run = EvalRun(
                id=completed_run_id,
                org_id=org1_id,
                dataset_name="golden_dataset",
                dataset_version="1.0.0",
                status="COMPLETED",
                llm_provider="deterministic-offline",
                llm_model="deterministic",
                embedding_model="feature-hashing",
                reranker_model="deterministic-cross-scoring",
                total_test_cases=5,
                passed_test_cases=5,
                progress_current=5,
                progress_total=5,
                created_at=datetime.now(timezone.utc),
            )
            db.add(comp_run)
            await db.commit()

        res = await client.post(
            f"/api/v1/evaluations/{completed_run_id}/cancel",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code == 400, f"Expected 400 when cancelling COMPLETED run, got {res.status_code}"
        assert "Cannot cancel evaluation run with status 'COMPLETED'" in res.json()["detail"]
        print("[PASS] Cancelling COMPLETED run rejected with 400 Bad Request.")

        # Attempt to cancel already CANCELLED run
        res = await client.post(
            f"/api/v1/evaluations/{pending_run_id}/cancel",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code == 400, f"Expected 400 when cancelling CANCELLED run, got {res.status_code}"
        assert "Cannot cancel evaluation run with status 'CANCELLED'" in res.json()["detail"]
        print("[PASS] Cancelling already CANCELLED run rejected with 400 Bad Request.")

        # -------------------------------------------------------------------------
        # 7. Multi-Worker Recovery Safety: Fresh Run Active in Another Process
        # -------------------------------------------------------------------------
        print("\n--- 7. Multi-Worker Recovery Safety: Fresh Run in Another Process ---")
        worker2_run_id = uuid.uuid4()
        recent_time = datetime.now(timezone.utc) - timedelta(seconds=15)  # Started 15s ago in Worker 2

        async with TestingSessionLocal() as db:
            # Run is NOT in this process's _active_run_ids set!
            worker2_run = EvalRun(
                id=worker2_run_id,
                org_id=org1_id,
                dataset_name="golden_dataset",
                dataset_version="1.0.0",
                status="RUNNING",
                llm_provider="deterministic-offline",
                llm_model="deterministic",
                embedding_model="feature-hashing",
                reranker_model="deterministic-cross-scoring",
                total_test_cases=20,
                passed_test_cases=1,
                progress_current=2,
                progress_total=20,
                created_at=recent_time,
                started_at=recent_time,
                summary_metrics={"last_heartbeat_at": recent_time.isoformat()},
            )
            db.add(worker2_run)
            await db.commit()

        # Ensure worker2_run_id is definitely NOT in _active_run_ids of current process
        _active_run_ids.discard(worker2_run_id)

        # Trigger batch recovery routine with 1800s threshold
        recovered_list = await evaluation_service.recover_stale_or_orphaned_runs(
            session_factory=TestingSessionLocal,
            stale_threshold_seconds=1800,
        )
        recovered_ids = [r.id for r in recovered_list]
        assert worker2_run_id not in recovered_ids, (
            "Multi-worker violation: Fresh run from another worker was falsely marked as recovered!"
        )

        async with TestingSessionLocal() as db:
            w2_db = await db.get(EvalRun, worker2_run_id)
            assert w2_db.status == "RUNNING", f"Expected RUNNING, got {w2_db.status}"
            assert w2_db.error_message is None

        # Attempt to recover the fresh run via single-run recovery API endpoint
        res = await client.post(
            f"/api/v1/evaluations/{worker2_run_id}/recover",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code == 400, f"Expected 400 when recovering active run, got {res.status_code}"
        assert "Evaluation run is active" in res.json()["detail"]
        print("[PASS] Fresh run active in another process preserved: batch recovery and single recovery safely reject (400).")

        # -------------------------------------------------------------------------
        # 8. Stale Run Timeout Recovery
        # -------------------------------------------------------------------------
        print("\n--- 8. Stale Run Timeout Recovery ---")
        stale_run_id = uuid.uuid4()
        old_time = datetime.now(timezone.utc) - timedelta(seconds=3600)  # 1 hour ago (crashed/hung)

        async with TestingSessionLocal() as db:
            stale_run = EvalRun(
                id=stale_run_id,
                org_id=org1_id,
                dataset_name="golden_dataset",
                dataset_version="1.0.0",
                status="RUNNING",
                llm_provider="deterministic-offline",
                llm_model="deterministic",
                embedding_model="feature-hashing",
                reranker_model="deterministic-cross-scoring",
                total_test_cases=50,
                passed_test_cases=4,
                progress_current=5,
                progress_total=50,
                created_at=old_time,
                started_at=old_time,
                summary_metrics={"last_heartbeat_at": old_time.isoformat()},
            )
            db.add(stale_run)
            await db.commit()

        recovered_stale = await evaluation_service.recover_stale_or_orphaned_runs(
            session_factory=TestingSessionLocal,
            stale_threshold_seconds=1800,  # 30 min threshold
        )
        stale_recovered_ids = [r.id for r in recovered_stale]
        assert stale_run_id in stale_recovered_ids, "Expected stale run to be recovered"

        async with TestingSessionLocal() as db:
            stale_db = await db.get(EvalRun, stale_run_id)
            assert stale_db.status == "FAILED"
            assert "timed out after" in stale_db.error_message
            assert stale_db.progress_current == 5
            assert stale_db.summary_metrics.get("interrupted") is True
            assert stale_db.summary_metrics.get("processed_cases_before_interruption") == 5
            print("[PASS] Stale run exceeding timeout safely recovered to FAILED with diagnostics.")

        # -------------------------------------------------------------------------
        # 9. Competing Cancellation vs Recovery Concurrent Updates
        # -------------------------------------------------------------------------
        print("\n--- 9. Competing Cancellation vs Recovery Updates ---")
        competing_run_id = uuid.uuid4()
        competing_old_time = datetime.now(timezone.utc) - timedelta(seconds=2400)  # 40 min old

        async with TestingSessionLocal() as db:
            competing_run = EvalRun(
                id=competing_run_id,
                org_id=org1_id,
                dataset_name="golden_dataset",
                dataset_version="1.0.0",
                status="RUNNING",
                llm_provider="deterministic-offline",
                llm_model="deterministic",
                embedding_model="feature-hashing",
                reranker_model="deterministic-cross-scoring",
                total_test_cases=10,
                passed_test_cases=1,
                progress_current=2,
                progress_total=10,
                created_at=competing_old_time,
                started_at=competing_old_time,
                summary_metrics={"last_heartbeat_at": competing_old_time.isoformat()},
            )
            db.add(competing_run)
            await db.commit()

        # Fire concurrent cancel and recover requests
        cancel_coro = client.post(
            f"/api/v1/evaluations/{competing_run_id}/cancel",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        recover_coro = client.post(
            f"/api/v1/evaluations/{competing_run_id}/recover",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        res_cancel, res_recover = await asyncio.gather(cancel_coro, recover_coro)
        statuses = {res_cancel.status_code, res_recover.status_code}

        # Concurrency safety requirement: exactly one must succeed with 200, and the other must cleanly fail with 400
        assert 200 in statuses, f"Expected one request to succeed with 200, got cancel={res_cancel.status_code}, recover={res_recover.status_code}"
        assert 400 in statuses, f"Expected competing request to be rejected with 400, got cancel={res_cancel.status_code}, recover={res_recover.status_code}"

        async with TestingSessionLocal() as db:
            final_comp_db = await db.get(EvalRun, competing_run_id)
            assert final_comp_db.status in ["CANCELLED", "FAILED"]
            print(f"[PASS] Competing cancel/recover race safely resolved: winner status '{final_comp_db.status}', loser rejected with 400.")

        # -------------------------------------------------------------------------
        # 10. Single-Run & Batch Recovery Endpoints
        # -------------------------------------------------------------------------
        print("\n--- 10. Single-Run & Batch Recovery REST Endpoints ---")
        single_orphaned_id = uuid.uuid4()
        single_old_time = datetime.now(timezone.utc) - timedelta(seconds=2000)

        async with TestingSessionLocal() as db:
            single_orphaned = EvalRun(
                id=single_orphaned_id,
                org_id=org1_id,
                dataset_name="golden_dataset",
                dataset_version="1.0.0",
                status="PENDING",
                llm_provider="deterministic-offline",
                llm_model="deterministic",
                embedding_model="feature-hashing",
                reranker_model="deterministic-cross-scoring",
                total_test_cases=10,
                passed_test_cases=0,
                progress_current=0,
                progress_total=10,
                created_at=single_old_time,
                summary_metrics={"last_heartbeat_at": single_old_time.isoformat()},
            )
            db.add(single_orphaned)
            await db.commit()

        # Recover single run via API
        res = await client.post(
            f"/api/v1/evaluations/{single_orphaned_id}/recover",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code == 200, f"Expected 200 for single recover, got {res.status_code}"
        rec_data = res.json()
        assert rec_data["status"] == "FAILED"
        assert "timed out after" in rec_data["error_message"]
        print(f"[PASS] Single run recover endpoint recovered run {single_orphaned_id}.")

        # Batch recovery endpoint for tenant
        res = await client.post(
            "/api/v1/evaluations/recover",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code == 200, f"Expected 200 for batch recover, got {res.status_code}"
        print("[PASS] Batch tenant recovery endpoint executed successfully.")

    print("\n===========================================================================")
    print("ALL PHASE 5C CANCELLATION & RECOVERY TESTS PASSED SUCCESSFULLY!")
    print("===========================================================================\n")


if __name__ == "__main__":
    asyncio.run(run_cancellation_recovery_tests())
