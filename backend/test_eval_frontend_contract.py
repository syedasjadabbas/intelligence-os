"""
Contract verification suite ensuring backend Evaluation API schemas strictly match
the TypeScript interfaces expected by the Next.js frontend client (lib/api.ts).
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


async def test_frontend_contracts():
    print("=" * 75)
    print("INTELLIGENCE OS - EVALUATION FRONTEND CONTRACT VERIFICATION")
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

    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    run1_id = uuid.uuid4()
    run2_id = uuid.uuid4()
    res_id = uuid.uuid4()

    async with TestingSessionLocal() as db:
        org = Organization(id=org_id, name="Contract Lab", slug="contract-lab")
        user = User(
            id=user_id,
            org_id=org_id,
            email="tester@contract.com",
            hashed_password=get_password_hash("Secret123!"),
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add_all([org, user])
        await db.flush()

        run1 = EvalRun(
            id=run1_id,
            org_id=org_id,
            dataset_name="golden_dataset",
            dataset_version="2.0.0",
            status="COMPLETED",
            total_test_cases=10,
            passed_test_cases=9,
            recall_at_3=0.90,
            recall_at_5=0.95,
            mrr=0.92,
            ndcg_at_5=0.94,
            mean_faithfulness=0.97,
            mean_correctness=0.95,
            mean_completeness=0.93,
            mean_citation_correctness=0.98,
            mean_latency_ms=230.0,
            latency_p95_ms=280.0,
            config_snapshot={"judge": "DeterministicJudge"},
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        run2 = EvalRun(
            id=run2_id,
            org_id=org_id,
            dataset_name="golden_dataset",
            dataset_version="2.0.0",
            status="COMPLETED",
            total_test_cases=10,
            passed_test_cases=10,
            recall_at_3=0.95,
            recall_at_5=1.00,
            mrr=0.98,
            ndcg_at_5=0.99,
            mean_faithfulness=1.00,
            mean_correctness=0.98,
            mean_completeness=0.97,
            mean_citation_correctness=1.00,
            mean_latency_ms=210.0,
            latency_p95_ms=250.0,
            config_snapshot={"judge": "DeterministicJudge"},
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        db.add_all([run1, run2])
        await db.flush()

        result1 = EvalRunResult(
            id=res_id,
            run_id=run1_id,
            org_id=org_id,
            test_case_id="TC-DEMO-01",
            query="What is the nanite composition in Mark LXXXV?",
            query_type="single_hop",
            expected_behavior="answer",
            generated_answer="Gold-titanium alloy lattice infused with carbon nanotubes.",
            passed=True,
            is_refusal=False,
            recall_at_3=1.0,
            recall_at_5=1.0,
            mrr=1.0,
            ndcg_at_5=1.0,
            citation_precision=1.0,
            citation_coverage=1.0,
            faithfulness=1.0,
            correctness=1.0,
            completeness=1.0,
            citation_correctness=1.0,
            total_latency_ms=185.2,
            retrieved_candidates=[
                {
                    "chunk_id": str(uuid.uuid4()),
                    "document_title": "mark_85_specs.pdf",
                    "section_heading": "NANITE COMPOSITION",
                    "content": "Gold-titanium alloy lattice infused with carbon nanotubes.",
                    "score": 0.045,
                }
            ],
            reranked_candidates=[
                {
                    "chunk_id": str(uuid.uuid4()),
                    "document_title": "mark_85_specs.pdf",
                    "section_heading": "NANITE COMPOSITION",
                    "content": "Gold-titanium alloy lattice infused with carbon nanotubes.",
                    "score": 0.045,
                    "rerank_score": 0.982,
                }
            ],
            citations=[
                {
                    "document_title": "mark_85_specs.pdf",
                    "page_number": 3,
                    "section_heading": "NANITE COMPOSITION",
                    "content": "Gold-titanium alloy lattice infused with carbon nanotubes.",
                }
            ],
            trace_data={"position_shift": 1, "promoted_to_top3": True},
            judge_output={"reasoning": "Accurate ground-truth match.", "supported": True},
        )
        db.add(result1)
        await db.commit()

    token = create_access_token(subject=user_id, org_id=org_id, role="ADMIN")
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        # Contract 1: List Runs Page
        print("\n--- 1. Contract: EvaluationRunsPage ---")
        list_res = await client.get("/api/v1/evaluations", headers=headers)
        assert list_res.status_code == 200
        list_data = list_res.json()
        assert "items" in list_data
        assert "total" in list_data
        assert "skip" in list_data
        assert "limit" in list_data

        item = list_data["items"][0]
        required_item_keys = [
            "id", "org_id", "dataset_name", "dataset_version", "status",
            "judge_type", "total_test_cases", "passed_test_cases", "pass_rate",
            "recall_at_5", "ndcg_at_5", "mean_faithfulness", "created_at"
        ]
        for key in required_item_keys:
            assert key in item, f"Missing key in EvaluationRunListItem: {key}"
        print("[PASS] EvaluationRunsPage contract matches TypeScript interface.")

        # Contract 2: Run Detail
        print("\n--- 2. Contract: EvaluationRunDetail ---")
        detail_res = await client.get(f"/api/v1/evaluations/{run1_id}", headers=headers)
        assert detail_res.status_code == 200
        detail_data = detail_res.json()
        required_detail_keys = [
            "id", "org_id", "dataset_name", "dataset_version", "status",
            "judge_type", "total_test_cases", "passed_test_cases", "pass_rate",
            "recall_at_3", "recall_at_5", "mrr", "ndcg_at_5",
            "mean_faithfulness", "mean_correctness", "mean_completeness",
            "mean_citation_correctness", "mean_latency_ms", "latency_p95_ms",
            "config_snapshot", "summary_metrics", "created_at"
        ]
        for key in required_detail_keys:
            assert key in detail_data, f"Missing key in EvaluationRunDetail: {key}"
        print("[PASS] EvaluationRunDetail contract matches TypeScript interface.")

        # Contract 3: Results Page
        print("\n--- 3. Contract: EvaluationResultsPage ---")
        results_res = await client.get(f"/api/v1/evaluations/{run1_id}/results", headers=headers)
        assert results_res.status_code == 200
        results_data = results_res.json()
        assert "items" in results_data
        assert "total" in results_data

        res_item = results_data["items"][0]
        required_res_keys = [
            "id", "run_id", "test_case_id", "query", "query_type",
            "expected_behavior", "generated_answer", "passed", "is_refusal",
            "recall_at_5", "ndcg_at_5", "faithfulness", "correctness",
            "total_latency_ms", "created_at"
        ]
        for key in required_res_keys:
            assert key in res_item, f"Missing key in EvaluationResultListItem: {key}"
        print("[PASS] EvaluationResultsPage contract matches TypeScript interface.")

        # Contract 4: Result Detail
        print("\n--- 4. Contract: EvaluationResultDetail ---")
        res_detail = await client.get(f"/api/v1/evaluations/{run1_id}/results/{res_id}", headers=headers)
        assert res_detail.status_code == 200
        detail_case = res_detail.json()
        required_case_keys = [
            "id", "run_id", "org_id", "test_case_id", "query", "query_type",
            "expected_behavior", "generated_answer", "passed", "is_refusal",
            "retrieved_candidates", "reranked_candidates", "citations",
            "trace_data", "judge_output", "created_at"
        ]
        for key in required_case_keys:
            assert key in detail_case, f"Missing key in EvaluationResultDetail: {key}"
        print("[PASS] EvaluationResultDetail contract matches TypeScript interface.")

        # Contract 5: Run Comparison
        print("\n--- 5. Contract: EvaluationComparisonResponse ---")
        comp_res = await client.get(
            f"/api/v1/evaluations/compare?base_run_id={run1_id}&target_run_id={run2_id}",
            headers=headers,
        )
        assert comp_res.status_code == 200
        comp_data = comp_res.json()
        assert "base_run" in comp_data
        assert "target_run" in comp_data
        assert "deltas" in comp_data
        assert "regressed_cases_count" in comp_data
        assert "improved_cases_count" in comp_data

        required_delta_keys = [
            "pass_rate", "recall_at_3", "recall_at_5", "mrr", "ndcg_at_5",
            "citation_precision", "citation_coverage", "mean_faithfulness",
            "mean_correctness", "mean_completeness", "mean_citation_correctness",
            "mean_latency_ms"
        ]
        for metric in required_delta_keys:
            assert metric in comp_data["deltas"], f"Missing delta for {metric}"
            d_obj = comp_data["deltas"][metric]
            assert "base_value" in d_obj
            assert "target_value" in d_obj
            assert "delta" in d_obj
            assert "status" in d_obj
            assert d_obj["status"] in ["improved", "regressed", "neutral"]
        print("[PASS] EvaluationComparisonResponse contract matches TypeScript interface.")

    print("\n" + "=" * 75)
    print("ALL EVALUATION FRONTEND CONTRACT CHECKS PASSED!")
    print("=" * 75)


if __name__ == "__main__":
    asyncio.run(test_frontend_contracts())
