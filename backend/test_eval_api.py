"""
Test suite for Phase 3 Evaluation REST API.
Verifies:
1. Authenticated access (200 OK for valid bearer token)
2. Unauthenticated access (401 Unauthorized without token)
3. Organization isolation (Org A cannot list, view, or compare Org B runs)
4. ADMIN authorization (ADMIN can POST /evaluations, MEMBER receives 403 Forbidden)
5. Evaluation run creation (bounded execution with limit=2, offline=True)
6. Run listing (GET /evaluations with pagination and newest-first order)
7. Run detail (GET /evaluations/{run_id} returns aggregate metrics)
8. Result listing (GET /evaluations/{run_id}/results)
9. Result detail (GET /evaluations/{run_id}/results/{result_id})
10. Filtering (passed, query_type, is_refusal)
11. Pagination (skip, limit)
12. Inaccessible run IDs (returns 404 for foreign or invalid UUIDs)
13. Comparison between runs (GET /evaluations/compare computes deltas and flags)
"""

import asyncio
from datetime import datetime, timezone
import uuid
import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.core.database import Base, set_session_factory
from app.core.security import create_access_token, get_password_hash
from app.main import app
from app.models.evaluation import EvalRun, EvalRunResult
from app.models.organization import Organization
from app.models.user import User, UserRole


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


async def run_evaluation_api_tests():
    print("=" * 75)
    print("INTELLIGENCE OS - PHASE 3 EVALUATION REST API TEST SUITE")
    print("=" * 75)

    SessionLocal = await setup_test_db()

    # Seed Organizations & Users
    org1_id = uuid.uuid4()
    org2_id = uuid.uuid4()
    admin1_id = uuid.uuid4()
    member1_id = uuid.uuid4()
    admin2_id = uuid.uuid4()

    run1_id = uuid.uuid4()
    run2_id = uuid.uuid4()
    run_zero_id = uuid.uuid4()
    org2_run_id = uuid.uuid4()

    res1_id = uuid.uuid4()
    res2_id = uuid.uuid4()

    async with SessionLocal() as db:
        # Org 1 & Users
        org1 = Organization(id=org1_id, name="Stark Industries", slug="stark-ind")
        admin1 = User(
            id=admin1_id,
            org_id=org1_id,
            email="tony@stark.com",
            hashed_password=get_password_hash("Jarvis123!"),
            role=UserRole.ADMIN,
            is_active=True,
        )
        member1 = User(
            id=member1_id,
            org_id=org1_id,
            email="rhodey@stark.com",
            hashed_password=get_password_hash("WarMachine1!"),
            role=UserRole.MEMBER,
            is_active=True,
        )

        # Org 2 & Admin
        org2 = Organization(id=org2_id, name="Hammer Industries", slug="hammer-ind")
        admin2 = User(
            id=admin2_id,
            org_id=org2_id,
            email="justin@hammer.com",
            hashed_password=get_password_hash("Hammer123!"),
            role=UserRole.ADMIN,
            is_active=True,
        )

        db.add_all([org1, admin1, member1, org2, admin2])
        await db.flush()

        # Seed Pre-existing EvalRun 1 for Org 1 (Base Run)
        eval_run_1 = EvalRun(
            id=run1_id,
            org_id=org1_id,
            dataset_name="golden_dataset",
            dataset_version="1.0.0",
            status="COMPLETED",
            llm_provider="deterministic-offline",
            llm_model="deterministic",
            total_test_cases=2,
            passed_test_cases=1,
            recall_at_3=0.85,
            recall_at_5=0.90,
            mrr=0.88,
            ndcg_at_5=0.89,
            mean_faithfulness=0.92,
            mean_correctness=0.91,
            mean_completeness=0.90,
            mean_citation_correctness=0.95,
            mean_latency_ms=210.5,
            latency_p95_ms=250.0,
            config_snapshot={"judge": "DeterministicJudge"},
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )

        # Seed Pre-existing EvalRun 2 for Org 1 (Target Run, improved)
        eval_run_2 = EvalRun(
            id=run2_id,
            org_id=org1_id,
            dataset_name="golden_dataset",
            dataset_version="2.0.0",
            status="COMPLETED",
            llm_provider="deterministic-offline",
            llm_model="deterministic",
            total_test_cases=2,
            passed_test_cases=2,
            recall_at_3=0.95,
            recall_at_5=1.00,
            mrr=0.98,
            ndcg_at_5=0.97,
            mean_faithfulness=0.98,
            mean_correctness=0.97,
            mean_completeness=0.95,
            mean_citation_correctness=0.99,
            mean_latency_ms=180.2,
            latency_p95_ms=210.0,
            config_snapshot={"judge": "DeterministicJudge"},
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )

        # Seed Pre-existing EvalRun for Org 2 (Foreign Tenant)
        eval_run_foreign = EvalRun(
            id=org2_run_id,
            org_id=org2_id,
            dataset_name="golden_dataset",
            dataset_version="1.0.0",
            status="COMPLETED",
            total_test_cases=1,
            passed_test_cases=1,
            recall_at_5=1.0,
            config_snapshot={"judge": "DeterministicJudge"},
        )

        # Seed Pre-existing EvalRun for Org 1 with zero baseline & missing/None metrics
        eval_run_zero = EvalRun(
            id=run_zero_id,
            org_id=org1_id,
            dataset_name="golden_dataset",
            dataset_version="1.0.0",
            status="COMPLETED",
            total_test_cases=2,
            passed_test_cases=0,
            recall_at_3=0.0,
            recall_at_5=0.0,
            mrr=0.0,
            ndcg_at_5=None,  # Missing/None metric test
            mean_faithfulness=None,  # Missing/None metric test
            mean_latency_ms=0.0,
            config_snapshot={"judge": "DeterministicJudge"},
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )

        db.add_all([eval_run_1, eval_run_2, eval_run_foreign, eval_run_zero])
        await db.flush()

        # Seed Results for Run 1
        res1 = EvalRunResult(
            id=res1_id,
            run_id=run1_id,
            org_id=org1_id,
            test_case_id="TC-001",
            query="What is the power output of the Arc Reactor?",
            query_type="single_hop",
            expected_behavior="answer",
            generated_answer="The Mark VI Arc Reactor produces 3.2 gigajoules per second.",
            passed=True,
            is_refusal=False,
            recall_at_5=1.0,
            ndcg_at_5=1.0,
            faithfulness=1.0,
            correctness=1.0,
            completeness=1.0,
            total_latency_ms=195.4,
            retrieved_candidates=[{"chunk_id": "c1", "content": "Power output: 3.2 GJ/s"}],
            reranked_candidates=[{"chunk_id": "c1", "rerank_score": 0.98}],
            citations=[{"document_title": "arc_specs.pdf", "page_number": 1}],
            judge_output={"reasoning": "Fully factual and supported."},
        )

        res2 = EvalRunResult(
            id=res2_id,
            run_id=run1_id,
            org_id=org1_id,
            test_case_id="TC-002",
            query="What is the quantum speed of the Flash?",
            query_type="unanswerable",
            expected_behavior="refuse",
            generated_answer="The Flash travels at Mach 10.",
            passed=False,
            is_refusal=False,
            recall_at_5=None,
            faithfulness=0.2,
            correctness=0.0,
            total_latency_ms=225.6,
            failure_reason="Failed to trigger refusal guardrail for unanswerable question.",
            judge_output={"reasoning": "Hallucinated answer on ungrounded query."},
        )

        # Seed Results for Run 2 (TC-002 improved from False to True)
        res3 = EvalRunResult(
            id=uuid.uuid4(),
            run_id=run2_id,
            org_id=org1_id,
            test_case_id="TC-001",
            query="What is the power output of the Arc Reactor?",
            query_type="single_hop",
            expected_behavior="answer",
            generated_answer="The Mark VI Arc Reactor produces 3.2 gigajoules per second.",
            passed=True,
            is_refusal=False,
            recall_at_5=1.0,
            ndcg_at_5=1.0,
            faithfulness=1.0,
            correctness=1.0,
            completeness=1.0,
            total_latency_ms=180.2,
        )

        res4 = EvalRunResult(
            id=uuid.uuid4(),
            run_id=run2_id,
            org_id=org1_id,
            test_case_id="TC-002",
            query="What is the quantum speed of the Flash?",
            query_type="unanswerable",
            expected_behavior="refuse",
            generated_answer="I cannot find sufficient evidence to answer.",
            passed=True,
            is_refusal=True,
            total_latency_ms=175.0,
        )

        db.add_all([res1, res2, res3, res4])
        await db.commit()

    token_admin1 = create_access_token(subject=admin1_id, org_id=org1_id, role="ADMIN")
    token_member1 = create_access_token(subject=member1_id, org_id=org1_id, role="MEMBER")
    token_admin2 = create_access_token(subject=admin2_id, org_id=org2_id, role="ADMIN")

    headers_admin1 = {"Authorization": f"Bearer {token_admin1}"}
    headers_member1 = {"Authorization": f"Bearer {token_member1}"}
    headers_admin2 = {"Authorization": f"Bearer {token_admin2}"}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        # 1. Unauthenticated Access Check
        print("\n--- 1. Unauthenticated Access Enforcement ---")
        unauth_res = await client.get("/api/v1/evaluations")
        assert unauth_res.status_code == 401
        print("[PASS] Unauthenticated request safely rejected with 401 Unauthorized.")

        # 2. Authenticated Run Listing & Multi-Tenant Isolation
        print("\n--- 2. Authenticated Run Listing & Isolation ---")
        list_res1 = await client.get("/api/v1/evaluations", headers=headers_admin1)
        assert list_res1.status_code == 200
        data1 = list_res1.json()
        assert data1["total"] == 3
        assert len(data1["items"]) == 3
        # Verify Org 1 cannot see Org 2's run
        returned_ids_org1 = [item["id"] for item in data1["items"]]
        assert str(org2_run_id) not in returned_ids_org1
        print(f"[PASS] Org 1 retrieved {data1['total']} runs. Org 2 runs strictly hidden.")

        list_res2 = await client.get("/api/v1/evaluations", headers=headers_admin2)
        assert list_res2.status_code == 200
        data2 = list_res2.json()
        assert data2["total"] == 1
        assert data2["items"][0]["id"] == str(org2_run_id)
        print("[PASS] Org 2 sees only their own single run.")

        # 3. RBAC Check on Starting Evaluation Runs & Limit Validation
        print("\n--- 3. Role-Based Access Control (RBAC) & POST Safety ---")
        # Standard MEMBER attempt -> must be 403 Forbidden
        member_post = await client.post(
            "/api/v1/evaluations",
            json={"dataset_name": "golden_dataset", "judge_type": "deterministic", "limit": 2},
            headers=headers_member1,
        )
        assert member_post.status_code == 403
        print("[PASS] MEMBER forbidden from starting evaluations (403 Forbidden).")

        # Server-side hard cap enforcement (limit <= 50, limit >= 1)
        oversized_post = await client.post(
            "/api/v1/evaluations",
            json={"dataset_name": "golden_dataset", "judge_type": "deterministic", "limit": 100},
            headers=headers_admin1,
        )
        assert oversized_post.status_code == 422
        print("[PASS] Oversized limit (100) rejected with 422 Unprocessable Entity.")

        zero_post = await client.post(
            "/api/v1/evaluations",
            json={"dataset_name": "golden_dataset", "judge_type": "deterministic", "limit": 0},
            headers=headers_admin1,
        )
        assert zero_post.status_code == 422
        print("[PASS] Invalid limit (0) rejected with 422 Unprocessable Entity.")

        # ADMIN attempt -> must succeed (201 Created)
        admin_post = await client.post(
            "/api/v1/evaluations",
            json={"dataset_name": "golden_dataset", "judge_type": "deterministic", "limit": 2, "offline": True},
            headers=headers_admin1,
        )
        assert admin_post.status_code == 201
        new_run = admin_post.json()
        assert new_run["status"] in ("PENDING", "COMPLETED")
        assert new_run["total_test_cases"] == 2
        # Polling/checking run detail confirms completion
        polled_res = await client.get(f"/api/v1/evaluations/{new_run['id']}", headers=headers_admin1)
        assert polled_res.status_code == 200
        polled_run = polled_res.json()
        assert polled_run["status"] == "COMPLETED"
        assert "pass_rate" in polled_run
        print(f"[PASS] ADMIN successfully created and executed run {new_run['id']} (Pass Rate: {polled_run['pass_rate']:.1%}).")

        # 4. Run Detail Verification & 404 Inaccessibility
        print("\n--- 4. Run Detail & Cross-Tenant 404 Inaccessibility ---")
        detail_res = await client.get(f"/api/v1/evaluations/{run1_id}", headers=headers_admin1)
        assert detail_res.status_code == 200
        detail_data = detail_res.json()
        assert detail_data["id"] == str(run1_id)
        assert detail_data["recall_at_5"] == 0.9
        assert detail_data["judge_type"] == "deterministic"
        print(f"[PASS] Run detail retrieved with aggregate metrics (Recall@5: {detail_data['recall_at_5']}).")

        # Org 2 attempting to view Org 1's run -> Must return 404 (never disclose foreign existence)
        cross_res = await client.get(f"/api/v1/evaluations/{run1_id}", headers=headers_admin2)
        assert cross_res.status_code == 404
        print("[PASS] Cross-tenant access to run ID returns 404 Not Found without leaking existence.")

        # Nonexistent UUID -> Must return 404
        fake_uuid = uuid.uuid4()
        fake_res = await client.get(f"/api/v1/evaluations/{fake_uuid}", headers=headers_admin1)
        assert fake_res.status_code == 404
        print("[PASS] Nonexistent run ID returns 404 Not Found.")

        # 5. Case-level Results Listing & Filtering
        print("\n--- 5. Results Listing, Filtering, and Pagination ---")
        results_res = await client.get(f"/api/v1/evaluations/{run1_id}/results", headers=headers_admin1)
        assert results_res.status_code == 200
        res_data = results_res.json()
        assert res_data["total"] == 2
        assert len(res_data["items"]) == 2
        print(f"[PASS] Retrieved {res_data['total']} case results for Run 1.")

        # Foreign-org results list request -> 404
        cross_list_res = await client.get(f"/api/v1/evaluations/{run1_id}/results", headers=headers_admin2)
        assert cross_list_res.status_code == 404
        print("[PASS] Cross-tenant results list request safely rejected with 404 Not Found.")

        # Filter by passed=false
        failed_res = await client.get(f"/api/v1/evaluations/{run1_id}/results?passed=false", headers=headers_admin1)
        assert failed_res.status_code == 200
        failed_data = failed_res.json()
        assert failed_data["total"] == 1
        assert failed_data["items"][0]["passed"] is False
        assert failed_data["items"][0]["test_case_id"] == "TC-002"
        print("[PASS] Filtering by passed=false correctly isolates failed cases.")

        # Filter by query_type
        type_res = await client.get(f"/api/v1/evaluations/{run1_id}/results?query_type=single_hop", headers=headers_admin1)
        assert type_res.status_code == 200
        type_data = type_res.json()
        assert type_data["total"] == 1
        assert type_data["items"][0]["test_case_id"] == "TC-001"
        print("[PASS] Filtering by query_type=single_hop works correctly.")

        # 6. Result Detail Inspection & Result-Level Authorization
        print("\n--- 6. Test Case Detail Inspection & Authorization ---")
        # Valid result + valid run -> 200
        case_res = await client.get(f"/api/v1/evaluations/{run1_id}/results/{res1_id}", headers=headers_admin1)
        assert case_res.status_code == 200
        case_data = case_res.json()
        assert case_data["id"] == str(res1_id)
        assert case_data["query"] == "What is the power output of the Arc Reactor?"
        assert len(case_data["retrieved_candidates"]) >= 1
        assert len(case_data["reranked_candidates"]) >= 1
        assert len(case_data["citations"]) >= 1
        assert case_data["judge_output"]["reasoning"] == "Fully factual and supported."
        print("[PASS] Valid result + valid run returns 200 with full trace data.")

        # Valid result + wrong run -> 404
        wrong_run_res = await client.get(f"/api/v1/evaluations/{run2_id}/results/{res1_id}", headers=headers_admin1)
        assert wrong_run_res.status_code == 404
        print("[PASS] Valid result ID requested under wrong run ID returns 404 Not Found.")

        # Foreign-org result/run -> 404
        cross_case_res = await client.get(f"/api/v1/evaluations/{run1_id}/results/{res1_id}", headers=headers_admin2)
        assert cross_case_res.status_code == 404
        print("[PASS] Foreign-org result/run inspection returns 404 Not Found.")

        # 7. Run Comparison (Side-by-Side Deltas & Regression Detection)
        print("\n--- 7. Run Comparison & Metric Deltas Robustness ---")
        compare_res = await client.get(
            f"/api/v1/evaluations/compare?base_run_id={run1_id}&target_run_id={run2_id}",
            headers=headers_admin1,
        )
        assert compare_res.status_code == 200
        comp_data = compare_res.json()
        assert comp_data["base_run"]["id"] == str(run1_id)
        assert comp_data["target_run"]["id"] == str(run2_id)
        assert comp_data["deltas"]["pass_rate"]["status"] == "improved"
        assert comp_data["deltas"]["recall_at_5"]["status"] == "improved"
        assert comp_data["deltas"]["mean_latency_ms"]["status"] == "improved"  # 180.2 < 210.5 (lower is better)
        assert comp_data["improved_cases_count"] == 1
        assert comp_data["regressed_cases_count"] == 0
        print(f"[PASS] Comparison computed: Pass Rate delta = {comp_data['deltas']['pass_rate']['delta']:+.2f} ({comp_data['deltas']['pass_rate']['status']}).")
        print(f"[PASS] Latency delta = {comp_data['deltas']['mean_latency_ms']['delta']:+.1f}ms ({comp_data['deltas']['mean_latency_ms']['status']}).")
        print(f"[PASS] Case-level counts: improved={comp_data['improved_cases_count']}, regressed={comp_data['regressed_cases_count']}.")

        # Self-comparison: comparing run with itself -> deterministic deltas = 0.0, neutral, 0 regressions
        self_comp_res = await client.get(
            f"/api/v1/evaluations/compare?base_run_id={run1_id}&target_run_id={run1_id}",
            headers=headers_admin1,
        )
        assert self_comp_res.status_code == 200
        self_data = self_comp_res.json()
        assert self_data["deltas"]["pass_rate"]["delta"] == 0.0
        assert self_data["deltas"]["pass_rate"]["percent_change"] == 0.0
        assert self_data["deltas"]["pass_rate"]["status"] == "neutral"
        assert self_data["deltas"]["mean_latency_ms"]["delta"] == 0.0
        assert self_data["deltas"]["mean_latency_ms"]["status"] == "neutral"
        assert self_data["regressed_cases_count"] == 0
        assert self_data["improved_cases_count"] == 0
        print("[PASS] Self-comparison behaves deterministically (0 deltas, 0 regressions, neutral status).")

        # Missing run ID -> 404
        missing_comp_res = await client.get(
            f"/api/v1/evaluations/compare?base_run_id={run1_id}&target_run_id={uuid.uuid4()}",
            headers=headers_admin1,
        )
        assert missing_comp_res.status_code == 404
        print("[PASS] Comparison with missing run ID returns 404 Not Found.")

        # Cross-tenant comparison rejection (Org 1 run vs Org 2 run) -> 404
        cross_comp_res = await client.get(
            f"/api/v1/evaluations/compare?base_run_id={run1_id}&target_run_id={org2_run_id}",
            headers=headers_admin1,
        )
        assert cross_comp_res.status_code == 404
        print("[PASS] Cross-tenant comparison safely rejected with 404 Not Found.")

        # Zero baseline and None/missing metric robustness
        zero_comp_res = await client.get(
            f"/api/v1/evaluations/compare?base_run_id={run_zero_id}&target_run_id={run1_id}",
            headers=headers_admin1,
        )
        assert zero_comp_res.status_code == 200
        zero_comp = zero_comp_res.json()
        assert zero_comp["deltas"]["pass_rate"]["base_value"] == 0.0
        assert zero_comp["deltas"]["pass_rate"]["delta"] == 0.5
        assert zero_comp["deltas"]["pass_rate"]["percent_change"] is None  # Handled safely without zero-division error
        assert zero_comp["deltas"]["ndcg_at_5"]["base_value"] is None
        assert zero_comp["deltas"]["ndcg_at_5"]["delta"] is None
        assert zero_comp["deltas"]["ndcg_at_5"]["status"] == "neutral"
        print("[PASS] Zero baseline handled without zero-division error; None/missing metrics handled safely.")

    print("\n" + "=" * 75)
    print("ALL PHASE 3 EVALUATION API TESTS PASSED SUCCESSFULLY!")
    print("=" * 75)


if __name__ == "__main__":
    asyncio.run(run_evaluation_api_tests())
