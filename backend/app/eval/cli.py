"""
Command Line Interface (CLI) for running Intelligence OS RAG evaluation benchmarks.
Supports offline deterministic mode and LLM-judge mode, subset execution via --limit,
and displays formatted diagnostic reports directly in the terminal.
"""
import argparse
import asyncio
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session_factory, init_db
from app.eval.judges import BaseJudge, DeterministicJudge, LLMJudge
from app.eval.metrics import evaluate_threshold
from app.eval.runner import EvalRunner
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.models.organization import Organization
from app.services.embedding_service import embedding_service, generate_deterministic_mock_embedding

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("eval-cli")


async def ensure_benchmark_data(db: AsyncSession, org: Organization, offline: bool = True) -> None:
    """
    Seeds initial benchmark reference documents for the evaluation organization if not present.
    Covers Arc Reactor, Iron Legion Avionics, and Mark LXXXV Armor specifications across pages.
    """
    docs_to_seed = [
        {
            "title": "arc_reactor_tech.pdf",
            "file_path": "/eval/fixtures/arc_reactor_tech.pdf",
            "chunks": [
                {
                    "page_number": 1,
                    "section_heading": "# ARC REACTOR FUSION SPECIFICATION",
                    "content": (
                        "The Arc Reactor utilizes palladium core containment to catalyze cold fusion reactions. "
                        "Plasma flux density reaches peak power output with minimal thermal dissipation. "
                        "The magnetic field coils maintain toroidal plasma equilibrium at 45 Tesla."
                    ),
                },
                {
                    "page_number": 2,
                    "section_heading": "# EMERGENCY COOLING AND HEAT EXCHANGERS",
                    "content": (
                        "Emergency shutdown requires rapid thermal dissipation through liquid nitrogen cooling circuits. "
                        "Automated cryogenic relief valves vent nitrogen when core temperature exceeds critical thresholds. "
                        "Auxiliary heat sinks absorb residual thermal load up to 1200 Kelvin."
                    ),
                },
                {
                    "page_number": 3,
                    "section_heading": "# POWER DISTRIBUTION AND GRID BUS ARCHITECTURE",
                    "content": (
                        "Superconducting bus conduits route raw power output directly to main capacitors. "
                        "Energy distribution switches automatically throttle load during voltage spikes. "
                        "Backup lithium-hydride accumulator cells maintain baseline telemetry during primary generator offline states."
                    ),
                },
            ],
        },
        {
            "title": "iron_legion_avionics.pdf",
            "file_path": "/eval/fixtures/iron_legion_avionics.pdf",
            "chunks": [
                {
                    "page_number": 1,
                    "section_heading": "# IRON LEGION AVIONICS AND SENSOR NETWORKS",
                    "content": (
                        "Autonomous drone avionics employ neural mesh navigation and localized sensor networks. "
                        "Decentralized flight algorithms ensure coordinated swarm tactics and perimeter defense. "
                        "Lidar telemetry operates at 905 nanometers with millimeter precision mapping."
                    ),
                },
                {
                    "page_number": 2,
                    "section_heading": "# SWARM FLIGHT FORMATION AND COMBAT PROTOCOLS",
                    "content": (
                        "Swarm formation Bravo synchronizes velocity vectors across all operational sentry units. "
                        "If the command drone signal degrades below 40 dBm, sub-units revert to autonomous waypoint patrolling. "
                        "Encrypted laser frequency hop links prevent hostile electronic warfare jamming."
                    ),
                },
                {
                    "page_number": 3,
                    "section_heading": "# PROPULSION AND REPULSOR VECTORING",
                    "content": (
                        "Micro-thruster repulsor assemblies provide 360-degree attitude control in supersonic sub-orbital flight. "
                        "Solid-state ion turbines deliver sustained atmospheric loiter time of up to 48 hours without refueling. "
                        "High-g dampening inertial compensators protect avionics hardware during rapid evasion maneuvers."
                    ),
                },
            ],
        },
        {
            "title": "mark_lxxxv_armor_specs.pdf",
            "file_path": "/eval/fixtures/mark_lxxxv_armor_specs.pdf",
            "chunks": [
                {
                    "page_number": 1,
                    "section_heading": "# NANOTECHNOLOGY COMPOSITE MATRIX",
                    "content": (
                        "The Mark LXXXV armor features a reconfigurable gold-titanium nanoparticle matrix. "
                        "Nanite injectors synthesize physical shields and energy blades on demand. "
                        "Sub-dermal shock absorption layers dissipate up to 85 gigajoules of kinetic impact force."
                    ),
                },
                {
                    "page_number": 2,
                    "section_heading": "# WEAPONS AND INTEGRATED POWER ROUTING",
                    "content": (
                        "Integrated repulsor beam emitters draw directly from the chest-mounted RT-unit. "
                        "The lightning refocuser dorsal apparatus concentrates external electrical energy into amplified repulsor discharge. "
                        "Vibranium-reinforced gauntlets withstand extreme mechanical stress during heavy orbital re-entry."
                    ),
                },
            ],
        },
    ]

    for doc_def in docs_to_seed:
        stmt = select(Document).where(
            Document.org_id == org.id,
            Document.title == doc_def["title"],
        )
        existing_doc = (await db.execute(stmt)).scalar_one_or_none()

        if existing_doc:
            chunk_stmt = select(DocumentChunk).where(DocumentChunk.document_id == existing_doc.id)
            existing_chunks = (await db.execute(chunk_stmt)).scalars().all()
            if len(existing_chunks) != len(doc_def["chunks"]):
                for ec in existing_chunks:
                    await db.delete(ec)
                await db.flush()

                for idx, c_def in enumerate(doc_def["chunks"]):
                    content = c_def["content"]
                    emb = generate_deterministic_mock_embedding(content) if offline else await embedding_service.generate_embedding(content)
                    chunk = DocumentChunk(
                        id=uuid.uuid4(),
                        document_id=existing_doc.id,
                        org_id=org.id,
                        chunk_index=idx,
                        content=content,
                        page_number=c_def["page_number"],
                        section_heading=c_def["section_heading"],
                        embedding=emb,
                    )
                    db.add(chunk)
                await db.commit()
                logger.info(f"Updated benchmark document '{doc_def['title']}' for Org '{org.name}'")
        else:
            doc = Document(
                id=uuid.uuid4(),
                org_id=org.id,
                title=doc_def["title"],
                file_path=doc_def["file_path"],
                file_size_bytes=1024,
                status=DocumentStatus.COMPLETED,
            )
            db.add(doc)
            await db.flush()

            for idx, c_def in enumerate(doc_def["chunks"]):
                content = c_def["content"]
                emb = generate_deterministic_mock_embedding(content) if offline else await embedding_service.generate_embedding(content)
                chunk = DocumentChunk(
                    id=uuid.uuid4(),
                    document_id=doc.id,
                    org_id=org.id,
                    chunk_index=idx,
                    content=content,
                    page_number=c_def["page_number"],
                    section_heading=c_def["section_heading"],
                    embedding=emb,
                )
                db.add(chunk)
            await db.commit()
            logger.info(f"Seeded benchmark document '{doc_def['title']}' for Org '{org.name}'")


def format_table(headers: List[str], rows: List[List[str]]) -> str:
    """Renders a formatted ASCII table with clean borders."""
    widths = [len(h) for h in headers]
    for row in rows:
        for idx, val in enumerate(row):
            widths[idx] = max(widths[idx], len(str(val)))

    sep = "+-" + "-+-".join("-" * w for w in widths) + "-+"
    header_line = "| " + " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)) + " |"

    data_lines = []
    for row in rows:
        line = "| " + " | ".join(str(val).ljust(widths[i]) for i, val in enumerate(row)) + " |"
        data_lines.append(line)

    return "\n".join([sep, header_line, sep] + data_lines + [sep])


async def execute_cli_run(
    dataset_path: str,
    org_slug: str,
    output_path: Optional[str] = None,
    offline: bool = True,
    judge_type: str = "deterministic",
    limit: Optional[int] = None,
) -> int:
    """Executes the evaluation run and displays the terminal report."""
    print("=" * 84)
    print("      INTELLIGENCE OS - RAG QUALITY EVALUATION BENCHMARK")
    print("=" * 84)

    # 1. Initialize DB and Session Factory
    await init_db()
    session_factory = get_session_factory()

    async with session_factory() as session:
        # 2. Resolve organization
        stmt = select(Organization).where(Organization.slug == org_slug)
        org = (await session.execute(stmt)).scalar_one_or_none()

        if not org:
            logger.info(f"Creating evaluation organization with slug '{org_slug}'...")
            org = Organization(
                id=uuid.uuid4(),
                name="Stark Industries",
                slug=org_slug,
            )
            session.add(org)
            await session.commit()
            await session.refresh(org)

        # 3. Ensure test benchmark documents exist
        await ensure_benchmark_data(session, org, offline=offline)

        # 4. Resolve dataset path
        ds_path = Path(dataset_path)
        if not ds_path.is_absolute():
            if not ds_path.exists():
                candidate = Path(__file__).parent / "benchmarks" / dataset_path
                if candidate.exists():
                    ds_path = candidate
                else:
                    candidate2 = Path("app/eval/benchmarks") / dataset_path
                    if candidate2.exists():
                        ds_path = candidate2

        if not ds_path.exists():
            print(f"[ERROR] Benchmark dataset not found at: {ds_path}")
            return 1

        # 5. Initialize Judge
        judge_instance: BaseJudge
        if judge_type.lower() == "llm":
            try:
                judge_instance = LLMJudge()
            except ValueError as val_err:
                print(f"\n[ERROR] Failed to initialize LLM Judge: {val_err}")
                print("Tip: Run with --judge deterministic or configure GEMINI_API_KEY/OPENAI_API_KEY.\n")
                return 1
        else:
            judge_instance = DeterministicJudge()

        print(f"Dataset Path : {ds_path.resolve()}")
        print(f"Tenant Org   : {org.name} (Slug: {org.slug}, ID: {org.id})")
        print(f"Judge Mode   : {judge_instance.__class__.__name__} ({judge_type})")
        print(f"Execution    : {'Deterministic / Offline' if offline else 'Live Pipeline'}")
        if limit:
            print(f"Subset Limit : {limit} cases")
        print("-" * 84)

        # 6. Execute Evaluation Run
        runner = EvalRunner(
            db=session,
            org_id=org.id,
            judge=judge_instance,
            offline=offline,
        )

        eval_run = await runner.run_benchmark(ds_path, limit=limit)

        # Fetch results for detailed table display
        await session.refresh(eval_run, ["results"])
        results = sorted(eval_run.results, key=lambda r: r.test_case_id)

        # 7. Print Itemized Results Table
        headers = ["Case ID", "Type", "Rec@5", "nDCG@5", "Faith", "Corr", "Compl", "Refusal", "Status", "Latency"]
        rows = []
        for r in results:
            status_str = "PASS" if r.passed else "FAIL"
            ref_str = "YES" if r.is_refusal else "NO"
            rec_str = f"{r.recall_at_5:.2f}" if r.recall_at_5 is not None else "-"
            ndcg_str = f"{r.ndcg_at_5:.2f}" if r.ndcg_at_5 is not None else "-"
            faith_str = f"{r.faithfulness:.2f}" if r.faithfulness is not None else "-"
            corr_str = f"{r.correctness:.2f}" if r.correctness is not None else "-"
            comp_str = f"{r.completeness:.2f}" if r.completeness is not None else "-"
            lat_str = f"{r.total_latency_ms:.1f}ms" if r.total_latency_ms is not None else "-"

            rows.append([
                r.test_case_id,
                r.query_type[:13],
                rec_str,
                ndcg_str,
                faith_str,
                corr_str,
                comp_str,
                ref_str,
                status_str,
                lat_str,
            ])

        judge_name = judge_instance.__class__.__name__
        judge_tag = f"[{judge_name}]"

        print(f"\n--- ITEM DETAIL EVALUATION RESULTS (Judge Mode: {judge_name}) ---")
        print(format_table(headers, rows))

        # 8. Print Aggregate Metrics Summary
        summary = eval_run.summary_metrics or {}
        summary_headers = ["Metric", "Value", "Benchmark Target", "Status"]
        pass_rate = summary.get("pass_rate", 0.0)

        summary_rows = [
            ["Total Test Cases", str(eval_run.total_test_cases), str(eval_run.total_test_cases), "COMPLETE"],
            ["Passed Test Cases", str(eval_run.passed_test_cases), f">={int(eval_run.total_test_cases * 0.9)}", evaluate_threshold(eval_run.passed_test_cases, int(eval_run.total_test_cases * 0.9), ">=")],
            ["Overall Pass Rate", f"{pass_rate:.1%}", ">= 90.0%", evaluate_threshold(pass_rate, 0.90, ">=")],
            ["Recall@3", f"{eval_run.recall_at_3 or 0.0:.4f}", ">= 0.8500", evaluate_threshold(eval_run.recall_at_3, 0.85, ">=", warn_target=0.75)],
            ["Recall@5", f"{eval_run.recall_at_5 or 0.0:.4f}", ">= 0.9000", evaluate_threshold(eval_run.recall_at_5, 0.90, ">=", warn_target=0.80)],
            ["Mean Reciprocal Rank (MRR)", f"{eval_run.mrr or 0.0:.4f}", ">= 0.8000", evaluate_threshold(eval_run.mrr, 0.80, ">=", warn_target=0.70)],
            ["nDCG@5", f"{eval_run.ndcg_at_5 or 0.0:.4f}", ">= 0.8500", evaluate_threshold(eval_run.ndcg_at_5, 0.85, ">=", warn_target=0.75)],
            ["Citation Precision", f"{eval_run.citation_precision or 0.0:.4f}", ">= 0.8500", evaluate_threshold(eval_run.citation_precision, 0.85, ">=", warn_target=0.75)],
            ["Citation Coverage", f"{eval_run.citation_coverage or 0.0:.4f}", ">= 0.9000", evaluate_threshold(eval_run.citation_coverage, 0.90, ">=", warn_target=0.80)],
            [f"Mean Faithfulness {judge_tag}", f"{eval_run.mean_faithfulness or 0.0:.4f}", ">= 0.9000", evaluate_threshold(eval_run.mean_faithfulness, 0.90, ">=", warn_target=0.80)],
            [f"Mean Correctness {judge_tag}", f"{eval_run.mean_correctness or 0.0:.4f}", ">= 0.8500", evaluate_threshold(eval_run.mean_correctness, 0.85, ">=", warn_target=0.75)],
            [f"Mean Completeness {judge_tag}", f"{eval_run.mean_completeness or 0.0:.4f}", ">= 0.8500", evaluate_threshold(eval_run.mean_completeness, 0.85, ">=", warn_target=0.75)],
            ["Correct Refusal Rate (CRR)", f"{eval_run.correct_refusal_rate or 0.0:.4f}", "1.0000", evaluate_threshold(eval_run.correct_refusal_rate, 1.0, "==")],
            ["False Refusal Rate (FRR)", f"{eval_run.false_refusal_rate or 0.0:.4f}", "<= 0.0500", evaluate_threshold(eval_run.false_refusal_rate, 0.05, "<=")],
            ["Mean Latency", f"{eval_run.mean_latency_ms or 0.0:.2f} ms", "< 250 ms", evaluate_threshold(eval_run.mean_latency_ms, 250.0, "<", warn_target=350.0)],
            ["P95 Latency", f"{eval_run.latency_p95_ms or 0.0:.2f} ms", "< 500 ms", evaluate_threshold(eval_run.latency_p95_ms, 500.0, "<", warn_target=750.0)],
        ]

        print(f"\n--- AGGREGATE EVALUATION SUMMARY (Judge Mode: {judge_name}) ---")
        print(format_table(summary_headers, summary_rows))

        # 9. Output to JSON file if requested
        if output_path:
            out_file = Path(output_path)
            out_file.parent.mkdir(parents=True, exist_ok=True)
            export_payload = {
                "run_id": str(eval_run.id),
                "dataset_name": eval_run.dataset_name,
                "dataset_version": eval_run.dataset_version,
                "status": eval_run.status,
                "judge": judge_instance.__class__.__name__,
                "total_test_cases": eval_run.total_test_cases,
                "passed_test_cases": eval_run.passed_test_cases,
                "summary_metrics": eval_run.summary_metrics,
                "results": [
                    {
                        "test_case_id": r.test_case_id,
                        "query": r.query,
                        "query_type": r.query_type,
                        "expected_behavior": r.expected_behavior,
                        "passed": r.passed,
                        "is_refusal": r.is_refusal,
                        "recall_at_3": r.recall_at_3,
                        "recall_at_5": r.recall_at_5,
                        "mrr": r.mrr,
                        "ndcg_at_5": r.ndcg_at_5,
                        "faithfulness": r.faithfulness,
                        "correctness": r.correctness,
                        "completeness": r.completeness,
                        "citation_precision": r.citation_precision,
                        "citation_coverage": r.citation_coverage,
                        "total_latency_ms": r.total_latency_ms,
                        "failure_reason": r.failure_reason,
                    }
                    for r in results
                ],
            }
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(export_payload, f, indent=2)
            print(f"\n[INFO] Detailed evaluation run exported to: {out_file.resolve()}")

    return 0 if (eval_run.passed_test_cases >= int(eval_run.total_test_cases * 0.85)) else 1


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        prog="python -m app.eval.cli",
        description="Intelligence OS Enterprise RAG Evaluation CLI Runner",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: run
    run_parser = subparsers.add_parser("run", help="Execute an evaluation benchmark run")
    run_parser.add_argument(
        "--dataset",
        type=str,
        default="golden_dataset.json",
        help="Path or filename of the benchmark dataset JSON (defaults to golden_dataset.json)",
    )
    run_parser.add_argument(
        "--org-slug",
        type=str,
        default="stark-industries",
        help="Tenant organization slug (defaults to stark-industries)",
    )
    run_parser.add_argument(
        "--offline",
        action="store_true",
        default=True,
        help="Run in offline deterministic mode with zero external network calls",
    )
    run_parser.add_argument(
        "--judge",
        type=str,
        choices=["deterministic", "llm"],
        default="deterministic",
        help="Judge evaluation strategy (deterministic or llm)",
    )
    run_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on the number of benchmark test cases to evaluate",
    )
    run_parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path to export the evaluation run results as JSON",
    )

    args = parser.parse_args()

    # Default to 'run' command if invoked without subcommands
    if not args.command:
        dataset = "golden_dataset.json"
        org_slug = "stark-industries"
        output = None
        offline = True
        judge = "deterministic"
        limit = None
    else:
        dataset = args.dataset
        org_slug = args.org_slug
        output = args.output
        offline = args.offline
        judge = getattr(args, "judge", "deterministic")
        limit = getattr(args, "limit", None)

    code = asyncio.run(
        execute_cli_run(
            dataset_path=dataset,
            org_slug=org_slug,
            output_path=output,
            offline=offline,
            judge_type=judge,
            limit=limit,
        )
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
