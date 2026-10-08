"""
End-to-end test suite for EvalRunner with Phase 2 features.
Verifies:
1. 50-case benchmark loading and evidence anchor resolution
2. Execution with DeterministicJudge and Mocked LLMJudge
3. Subset execution via limit (e.g. limit=10)
4. Phase 2 typed metrics persistence on EvalRun and EvalRunResult (nDCG@5, faithfulness, correctness, completeness, latency)
5. Tenant data isolation across organizations without external network calls
"""
import asyncio
import json
from pathlib import Path
import sys
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.eval.judges import DeterministicJudge, LLMJudge
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
        file_size_bytes=3072,
        status=DocumentStatus.COMPLETED,
    )
    doc2 = Document(
        id=uuid.uuid4(),
        org_id=org_stark.id,
        title="iron_legion_avionics.pdf",
        file_path="/eval/fixtures/iron_legion_avionics.pdf",
        file_size_bytes=3072,
        status=DocumentStatus.COMPLETED,
    )
    doc3 = Document(
        id=uuid.uuid4(),
        org_id=org_stark.id,
        title="mark_lxxxv_armor_specs.pdf",
        file_path="/eval/fixtures/mark_lxxxv_armor_specs.pdf",
        file_size_bytes=2048,
        status=DocumentStatus.COMPLETED,
    )
    session.add_all([doc1, doc2, doc3])
    await session.flush()

    # Chunks covering all 50 benchmark cases
    chunks_data = [
        # Arc Reactor Tech
        (
            doc1,
            1,
            "# ARC REACTOR FUSION SPECIFICATION",
            "The Arc Reactor utilizes palladium core containment to catalyze cold fusion reactions. "
            "Plasma flux density reaches peak power output with minimal thermal dissipation. "
            "The magnetic field coils maintain toroidal plasma equilibrium at 45 Tesla.",
        ),
        (
            doc1,
            2,
            "# EMERGENCY COOLING AND HEAT EXCHANGERS",
            "Emergency shutdown requires rapid thermal dissipation through liquid nitrogen cooling circuits. "
            "Automated cryogenic relief valves vent nitrogen when core temperature exceeds critical thresholds. "
            "Auxiliary heat sinks absorb residual thermal load up to 1200 Kelvin.",
        ),
        (
            doc1,
            3,
            "# POWER DISTRIBUTION AND GRID BUS ARCHITECTURE",
            "Superconducting bus conduits route raw power output directly to main capacitors. "
            "Energy distribution switches automatically throttle load during voltage spikes. "
            "Backup lithium-hydride accumulator cells maintain baseline telemetry during primary generator offline states.",
        ),
        # Iron Legion Avionics
        (
            doc2,
            1,
            "# IRON LEGION AVIONICS AND SENSOR NETWORKS",
            "Autonomous drone avionics employ neural mesh navigation and localized sensor networks. "
            "Decentralized flight algorithms ensure coordinated swarm tactics and perimeter defense. "
            "Lidar telemetry operates at 905 nanometers with millimeter precision mapping.",
        ),
        (
            doc2,
            2,
            "# SWARM FLIGHT FORMATION AND COMBAT PROTOCOLS",
            "Swarm formation Bravo synchronizes velocity vectors across all operational sentry units. "
            "If the command drone signal degrades below 40 dBm, sub-units revert to autonomous waypoint patrolling. "
            "Encrypted laser frequency hop links prevent hostile electronic warfare jamming.",
        ),
        (
            doc2,
            3,
            "# PROPULSION AND REPULSOR VECTORING",
            "Micro-thruster repulsor assemblies provide 360-degree attitude control in supersonic sub-orbital flight. "
            "Solid-state ion turbines deliver sustained atmospheric loiter time of up to 48 hours without refueling. "
            "High-g dampening inertial compensators protect avionics hardware during rapid evasion maneuvers.",
        ),
        # Mark LXXXV Armor Specs
        (
            doc3,
            1,
            "# NANOTECHNOLOGY COMPOSITE MATRIX",
            "The Mark LXXXV armor features a reconfigurable gold-titanium nanoparticle matrix. "
            "Nanite injectors synthesize physical shields and energy blades on demand. "
            "Sub-dermal shock absorption layers dissipate up to 85 gigajoules of kinetic impact force.",
        ),
        (
            doc3,
            2,
            "# WEAPONS AND INTEGRATED POWER ROUTING",
            "Integrated repulsor beam emitters draw directly from the chest-mounted RT-unit. "
            "The lightning refocuser dorsal apparatus concentrates external electrical energy into amplified repulsor discharge. "
            "Vibranium-reinforced gauntlets withstand extreme mechanical stress during heavy orbital re-entry.",
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
    print("=" * 80)
    print("INTELLIGENCE OS - PHASE 2 RAG EVALUATION RUNNER VERIFICATION SUITE")
    print("=" * 80)

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
    print("[PASS] In-memory SQLite database initialized with Phase 2 evaluation schema.")

    async with TestingSession() as session:
        # 2. Seed test tenants and data
        org_stark, org_wayne = await seed_test_tenant_and_docs(session)
        print(f"[PASS] Seeded Stark Industries ({org_stark.id}) and Wayne Enterprises ({org_wayne.id}).")

        # 3. Locate golden benchmark dataset
        dataset_path = Path(__file__).parent / "app" / "eval" / "benchmarks" / "golden_dataset.json"
        assert dataset_path.exists(), f"Benchmark dataset missing at {dataset_path}"

        # 4. Test 1: Sliced evaluation via limit (limit=10)
        print("\n--- Test 1: Sliced Evaluation with --limit 10 ---")
        runner_limited = EvalRunner(
            db=session,
            org_id=org_stark.id,
            judge=DeterministicJudge(),
            offline=True,
        )
        run_limited = await runner_limited.run_benchmark(dataset_path, limit=10, run_name="limited-10-run")
        assert run_limited.total_test_cases == 10, f"Expected 10 test cases, got {run_limited.total_test_cases}"
        assert run_limited.status == "COMPLETED"
        assert run_limited.ndcg_at_5 is not None
        assert run_limited.mean_faithfulness is not None
        assert run_limited.mean_correctness is not None
        assert run_limited.mean_completeness is not None
        print(f"[PASS] Sliced evaluation executed: {run_limited.passed_test_cases}/{run_limited.total_test_cases} passed. nDCG@5={run_limited.ndcg_at_5:.4f}")

        # 5. Test 2: Full 50-case Benchmark Evaluation
        print("\n--- Test 2: Full 50-case Benchmark Evaluation for Stark Industries ---")
        runner_full = EvalRunner(
            db=session,
            org_id=org_stark.id,
            judge=DeterministicJudge(),
            offline=True,
        )
        eval_run = await runner_full.run_benchmark(dataset_path, run_name="ci-verification-full-50")

        assert eval_run.id is not None
        assert eval_run.status == "COMPLETED"
        assert eval_run.total_test_cases == 50, f"Expected 50 test cases, got {eval_run.total_test_cases}"
        assert eval_run.passed_test_cases >= 45, f"Expected >= 45/50 passed, got {eval_run.passed_test_cases}"
        assert eval_run.recall_at_3 is not None and eval_run.recall_at_3 >= 0.85
        assert eval_run.recall_at_5 is not None and eval_run.recall_at_5 >= 0.90
        assert eval_run.mrr is not None and eval_run.mrr >= 0.80
        assert eval_run.ndcg_at_5 is not None and eval_run.ndcg_at_5 >= 0.85
        assert eval_run.citation_precision is not None and eval_run.citation_precision >= 0.85
        assert eval_run.citation_coverage is not None and eval_run.citation_coverage >= 0.90
        assert eval_run.correct_refusal_rate == 1.0, f"CRR must be 1.0, got {eval_run.correct_refusal_rate}"
        assert eval_run.false_refusal_rate == 0.0, f"FRR must be 0.0, got {eval_run.false_refusal_rate}"
        assert eval_run.mean_faithfulness is not None and eval_run.mean_faithfulness >= 0.90
        assert eval_run.mean_correctness is not None and eval_run.mean_correctness >= 0.80
        assert eval_run.mean_completeness is not None and eval_run.mean_completeness >= 0.80
        assert eval_run.mean_latency_ms is not None
        assert eval_run.latency_p95_ms is not None

        print(f"[PASS] EvalRun completed with {eval_run.passed_test_cases}/50 passed.")
        print(f"       Recall@5: {eval_run.recall_at_5:.4f} | nDCG@5: {eval_run.ndcg_at_5:.4f} | MRR: {eval_run.mrr:.4f}")
        print(f"       Mean Faithfulness: {eval_run.mean_faithfulness:.4f} | Correctness: {eval_run.mean_correctness:.4f} | Completeness: {eval_run.mean_completeness:.4f}")

        # 6. Verify EvalRunResult models in Database
        stmt = select(EvalRunResult).where(EvalRunResult.run_id == eval_run.id)
        results = (await session.execute(stmt)).scalars().all()
        assert len(results) == 50, f"Expected 50 persisted results, found {len(results)}"

        # Verify unanswerable queries were all refused
        unans_results = [r for r in results if r.query_type == "unanswerable"]
        assert len(unans_results) == 5
        for u in unans_results:
            assert u.is_refusal is True, f"Unanswerable case {u.test_case_id} was not refused"
            assert u.passed is True
            assert u.citations == []

        # Verify typed Phase 2 columns on item results
        for r in results:
            if r.expected_behavior == "answer":
                assert r.ndcg_at_5 is not None
            else:
                assert r.ndcg_at_5 is None
            assert r.faithfulness is not None
            assert r.correctness is not None
            assert r.completeness is not None

        print("[PASS] All 50 EvalRunResult records verified with Phase 2 typed metrics and JSON trace.")

        # 7. Test 3: LLMJudge Integration (Mocked)
        print("\n--- Test 3: Runner with Mocked LLMJudge ---")
        mock_json_response = json.dumps({
            "faithfulness": 0.98,
            "correctness": 0.95,
            "completeness": 0.90,
            "citation_correctness": 1.0,
            "supported": True,
            "reasoning": "High-fidelity RAG answer matching ground truth.",
            "unsupported_claims": [],
        })
        with patch("app.eval.judges.genai.GenerativeModel") as mock_gen_model:
            mock_inst = MagicMock()
            mock_resp = MagicMock()
            mock_resp.text = mock_json_response
            mock_inst.generate_content.return_value = mock_resp
            mock_gen_model.return_value = mock_inst

            llm_judge = LLMJudge(provider="gemini", api_key="mock-test-key")
            runner_llm = EvalRunner(
                db=session,
                org_id=org_stark.id,
                judge=llm_judge,
                offline=True,
            )
            run_llm = await runner_llm.run_benchmark(dataset_path, limit=3, run_name="llm-judge-test")
            assert run_llm.total_test_cases == 3
            assert run_llm.status == "COMPLETED"
            assert run_llm.mean_faithfulness == 0.98
            assert run_llm.mean_correctness == 0.95
            print(f"[PASS] Mocked LLMJudge execution confirmed: Mean Faithfulness={run_llm.mean_faithfulness}")

        # 8. Test 4: Multi-Tenant Isolation Verification
        print("\n--- Test 4: Verifying Tenant Data Isolation under Wayne Enterprises ---")
        runner_wayne = EvalRunner(
            db=session,
            org_id=org_wayne.id,
            judge=DeterministicJudge(),
            offline=True,
        )
        eval_run_wayne = await runner_wayne.run_benchmark(dataset_path, limit=10, run_name="wayne-isolation-check")

        # Wayne has zero documents -> All answerable queries must fail retrieval (Recall@5 = 0.0)
        stmt_w = select(EvalRunResult).where(EvalRunResult.run_id == eval_run_wayne.id)
        results_wayne = (await session.execute(stmt_w)).scalars().all()
        assert len(results_wayne) == 10

        stark_queries_under_wayne = [
            r for r in results_wayne if r.query_type != "unanswerable"
        ]
        for sw in stark_queries_under_wayne:
            # Wayne must NOT see Stark's documents
            assert sw.recall_at_5 == 0.0, f"Cross-tenant leak detected for test case {sw.test_case_id}!"
            assert sw.retrieved_candidates == [], f"Wayne retrieved chunks from Stark!"

        print("[PASS] Strict tenant isolation confirmed: 0 chunks leaked across organizations.")

    print("\n" + "=" * 80)
    print("ALL EVALUATION RUNNER VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_evaluation_runner_verification())
