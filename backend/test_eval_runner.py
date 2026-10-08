"""
End-to-end test suite for EvalRunner.
Verifies benchmark execution, anchor resolution, deterministic judging,
metric aggregation, database persistence into eval_runs and eval_run_results,
and tenant isolation without external network or API dependencies.
"""
import asyncio
from pathlib import Path
import sys
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.eval.judges import DeterministicJudge
from app.eval.runner import EvalRunner
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.models.evaluation import EvalRun, EvalRunResult
from app.models.organization import Organization
from app.schemas.evaluation import BenchmarkDataset
from app.services.embedding_service import embedding_service


async def seed_test_tenant_and_docs(session: AsyncSession) -> tuple[Organization, Organization]:
    """Sets up two isolated tenant organizations with test documents in Org 1 only."""
    # Org 1: Stark Industries
    org_stark = Organization(
        id=uuid.uuid4(),
        name="Stark Industries",
        slug="stark-industries",
    )
    # Org 2: Wayne Enterprises (empty / isolated tenant)
    org_wayne = Organization(
        id=uuid.uuid4(),
        name="Wayne Enterprises",
        slug="wayne-enterprises",
    )
    session.add_all([org_stark, org_wayne])
    await session.flush()

    # Documents for Stark Industries
    doc1 = Document(
        id=uuid.uuid4(),
        org_id=org_stark.id,
        title="arc_reactor_tech.pdf",
        file_path="/eval/fixtures/arc_reactor_tech.pdf",
        file_size_bytes=2048,
        status=DocumentStatus.COMPLETED,
    )
    doc2 = Document(
        id=uuid.uuid4(),
        org_id=org_stark.id,
        title="iron_legion_avionics.pdf",
        file_path="/eval/fixtures/iron_legion_avionics.pdf",
        file_size_bytes=1024,
        status=DocumentStatus.COMPLETED,
    )
    session.add_all([doc1, doc2])
    await session.flush()

    # Chunks for Arc Reactor Tech
    chunks_data = [
        (
            doc1,
            1,
            "# ARC REACTOR FUSION SPECIFICATION",
            "The Arc Reactor utilizes palladium core containment to catalyze cold fusion reactions. "
            "Plasma flux density reaches peak power output with minimal thermal dissipation.",
        ),
        (
            doc1,
            2,
            "# EMERGENCY COOLING AND HEAT EXCHANGERS",
            "Emergency shutdown requires rapid thermal dissipation through liquid nitrogen cooling circuits. "
            "Automated cryogenic relief valves vent nitrogen when core temperature exceeds critical thresholds.",
        ),
        (
            doc2,
            1,
            "# IRON LEGION AVIONICS AND FLIGHT PROTOCOLS",
            "Autonomous drone avionics employ neural mesh navigation and localized sensor networks. "
            "Decentralized flight algorithms ensure coordinated swarm tactics and perimeter defense.",
        ),
    ]

    for idx, (doc, page, heading, text) in enumerate(chunks_data):
        emb = await embedding_service.generate_embedding(text)
        chunk = DocumentChunk(
            id=uuid.uuid4(),
            document_id=doc.id,
            org_id=org_stark.id,
            chunk_index=idx,
            content=text,
            page_number=page,
            section_heading=heading,
            embedding=emb,
        )
        session.add(chunk)

    await session.commit()
    return org_stark, org_wayne


async def run_evaluation_runner_verification():
    print("=" * 75)
    print("INTELLIGENCE OS - RAG EVALUATION RUNNER VERIFICATION SUITE")
    print("=" * 75)

    # 1. Setup isolated in-memory test database
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestingSession = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Build full multi-tenant schema including eval_runs and eval_run_results
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[PASS] In-memory SQLite database initialized with evaluation schema.")

    async with TestingSession() as session:
        # 2. Seed test tenants and data
        org_stark, org_wayne = await seed_test_tenant_and_docs(session)
        print(f"[PASS] Seeded Stark Industries ({org_stark.id}) and Wayne Enterprises ({org_wayne.id}).")

        # 3. Locate golden benchmark dataset
        dataset_path = Path(__file__).parent / "app" / "eval" / "benchmarks" / "golden_dataset.json"
        assert dataset_path.exists(), f"Benchmark dataset missing at {dataset_path}"

        # 4. Instantiate EvalRunner in offline mode
        runner = EvalRunner(
            db=session,
            org_id=org_stark.id,
            judge=DeterministicJudge(),
            offline=True,
        )

        print("\n--- Executing 15-case Benchmark Evaluation for Stark Industries ---")
        eval_run = await runner.run_benchmark(dataset_path, run_name="ci-verification-run-1")

        # 5. Verify EvalRun model fields
        assert eval_run.id is not None
        assert eval_run.status == "COMPLETED"
        assert eval_run.total_test_cases == 15
        assert eval_run.passed_test_cases == 15, f"Expected 15/15 passed, got {eval_run.passed_test_cases}"
        assert eval_run.recall_at_3 is not None and eval_run.recall_at_3 >= 0.85
        assert eval_run.recall_at_5 is not None and eval_run.recall_at_5 >= 0.90
        assert eval_run.mrr is not None and eval_run.mrr >= 0.80
        assert eval_run.citation_precision is not None and eval_run.citation_precision >= 0.85
        assert eval_run.citation_coverage is not None and eval_run.citation_coverage >= 0.90
        assert eval_run.correct_refusal_rate == 1.0, f"CRR must be 1.0, got {eval_run.correct_refusal_rate}"
        assert eval_run.false_refusal_rate == 0.0, f"FRR must be 0.0, got {eval_run.false_refusal_rate}"
        assert eval_run.latency_p95_ms is not None
        print(f"[PASS] EvalRun completed with {eval_run.passed_test_cases}/15 passed.")
        print(f"       Recall@5: {eval_run.recall_at_5:.4f} | MRR: {eval_run.mrr:.4f} | CRR: {eval_run.correct_refusal_rate:.4f} | FRR: {eval_run.false_refusal_rate:.4f}")

        # 6. Verify EvalRunResult models in Database
        stmt = select(EvalRunResult).where(EvalRunResult.run_id == eval_run.id)
        results = (await session.execute(stmt)).scalars().all()
        assert len(results) == 15, f"Expected 15 persisted results, found {len(results)}"

        # Verify unanswerable queries were all refused
        unans_results = [r for r in results if r.query_type == "unanswerable"]
        assert len(unans_results) == 5
        for u in unans_results:
            assert u.is_refusal is True, f"Unanswerable case {u.test_case_id} was not refused"
            assert u.passed is True
            assert u.citations == []

        # Verify single_hop and coreference queries passed and answered
        answerable_results = [r for r in results if r.query_type in ("single_hop", "coreference_followup")]
        assert len(answerable_results) == 10
        for a in answerable_results:
            assert a.is_refusal is False, f"Answerable case {a.test_case_id} was falsely refused"
            assert a.passed is True
            assert a.recall_at_5 == 1.0, f"Case {a.test_case_id} did not retrieve all ground truth anchors"
            assert len(a.citations) > 0, f"Case {a.test_case_id} missing citations"

        print("[PASS] All 15 EvalRunResult records verified with typed metrics and JSON trace.")

        # 7. Multi-Tenant Isolation Verification
        print("\n--- Verifying Tenant Data Isolation under Wayne Enterprises ---")
        runner_wayne = EvalRunner(
            db=session,
            org_id=org_wayne.id,
            judge=DeterministicJudge(),
            offline=True,
        )
        eval_run_wayne = await runner_wayne.run_benchmark(dataset_path, run_name="wayne-isolation-check")

        # Wayne has zero documents -> All answerable queries must fail retrieval (Recall@5 = 0.0)
        stmt_w = select(EvalRunResult).where(EvalRunResult.run_id == eval_run_wayne.id)
        results_wayne = (await session.execute(stmt_w)).scalars().all()
        assert len(results_wayne) == 15

        stark_queries_under_wayne = [
            r for r in results_wayne if r.query_type in ("single_hop", "coreference_followup")
        ]
        for sw in stark_queries_under_wayne:
            # Wayne must NOT see Stark's documents
            assert sw.recall_at_5 == 0.0, f"Cross-tenant leak detected for test case {sw.test_case_id}!"
            assert sw.retrieved_candidates == [], f"Wayne retrieved chunks from Stark!"

        print("[PASS] Strict tenant isolation confirmed: 0 chunks leaked across organizations.")

    print("\n" + "=" * 75)
    print("ALL EVALUATION RUNNER VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 75)


if __name__ == "__main__":
    asyncio.run(run_evaluation_runner_verification())
