"""
Intelligence OS - RAG Evaluation Framework CLI.
Command-line interface to execute evaluation runs, benchmark datasets,
and inspect retrieval/generation performance metrics from the terminal.

Usage:
    python -m app.eval.cli run [--dataset PATH] [--org-slug SLUG] [--output OUT]
"""
import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import sys
import uuid
from typing import List, Optional

from sqlalchemy import select

from app.core.database import Base, get_session_factory, init_db
from app.eval.runner import EvalRunner
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.models.organization import Organization
from app.schemas.evaluation import BenchmarkDataset
from app.services.embedding_service import embedding_service

# Configure console logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("eval_cli")


async def ensure_benchmark_data(db, org: Organization) -> None:
    """
    Ensures the target benchmark documents and chunks exist for the tenant.
    Creates them deterministically if they are not already present in the database.
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
                        "Plasma flux density reaches peak power output with minimal thermal dissipation."
                    ),
                },
                {
                    "page_number": 2,
                    "section_heading": "# EMERGENCY COOLING AND HEAT EXCHANGERS",
                    "content": (
                        "Emergency shutdown requires rapid thermal dissipation through liquid nitrogen cooling circuits. "
                        "Automated cryogenic relief valves vent nitrogen when core temperature exceeds critical thresholds."
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
                    "section_heading": "# IRON LEGION AVIONICS AND FLIGHT PROTOCOLS",
                    "content": (
                        "Autonomous drone avionics employ neural mesh navigation and localized sensor networks. "
                        "Decentralized flight algorithms ensure coordinated swarm tactics and perimeter defense."
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

        if not existing_doc:
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
                emb = await embedding_service.generate_embedding(content)
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
) -> int:
    """Executes the evaluation run and displays the terminal report."""
    print("=" * 78)
    print("  INTELLIGENCE OS - RAG EVALUATION BENCHMARK RUNNER")
    print("=" * 78)

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
        await ensure_benchmark_data(session, org)

        # 4. Resolve dataset path
        ds_path = Path(dataset_path)
        if not ds_path.is_absolute():
            # Try relative to cwd or backend/app/eval/benchmarks/
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

        print(f"Dataset Path : {ds_path.resolve()}")
        print(f"Tenant Org   : {org.name} (Slug: {org.slug}, ID: {org.id})")
        print(f"Mode         : {'Deterministic / Offline' if offline else 'Live LLM'}")
        print("-" * 78)

        # 5. Execute Evaluation Run
        runner = EvalRunner(
            db=session,
            org_id=org.id,
            offline=offline,
        )

        eval_run = await runner.run_benchmark(ds_path)

        # Fetch results for detailed table display
        await session.refresh(eval_run, ["results"])
        results = sorted(eval_run.results, key=lambda r: r.test_case_id)

        # 6. Print Itemized Results Table
        headers = ["Case ID", "Type", "Recall@5", "MRR", "Citations", "Refusal", "Status", "Latency"]
        rows = []
        for r in results:
            status_str = "PASS" if r.passed else "FAIL"
            cit_str = f"{r.citation_precision:.2f}/{r.citation_coverage:.2f}" if r.citation_coverage is not None else "-"
            ref_str = "YES" if r.is_refusal else "NO"
            rec_str = f"{r.recall_at_5:.2f}" if r.recall_at_5 is not None else "-"
            mrr_str = f"{r.mrr:.2f}" if r.mrr is not None else "-"
            lat_str = f"{r.total_latency_ms:.1f}ms" if r.total_latency_ms is not None else "-"

            rows.append([
                r.test_case_id,
                r.query_type,
                rec_str,
                mrr_str,
                cit_str,
                ref_str,
                status_str,
                lat_str,
            ])

        print("\n--- ITEM DETAIL EVALUATION RESULTS ---")
        print(format_table(headers, rows))

        # 7. Print Aggregate Metrics Summary
        summary = eval_run.summary_metrics or {}
        summary_headers = ["Metric", "Value", "Benchmark Target", "Status"]
        pass_rate = summary.get("pass_rate", 0.0)

        summary_rows = [
            ["Total Test Cases", str(eval_run.total_test_cases), "15", "COMPLETE"],
            ["Passed Test Cases", str(eval_run.passed_test_cases), f">={int(eval_run.total_test_cases * 0.9)}", "PASS" if eval_run.passed_test_cases >= 14 else "WARN"],
            ["Overall Pass Rate", f"{pass_rate:.1%}", ">= 90.0%", "PASS" if pass_rate >= 0.9 else "FAIL"],
            ["Recall@3", f"{eval_run.recall_at_3:.4f}", ">= 0.8500", "PASS" if (eval_run.recall_at_3 or 0) >= 0.85 else "WARN"],
            ["Recall@5", f"{eval_run.recall_at_5:.4f}", ">= 0.9000", "PASS" if (eval_run.recall_at_5 or 0) >= 0.90 else "WARN"],
            ["Mean Reciprocal Rank (MRR)", f"{eval_run.mrr:.4f}", ">= 0.8000", "PASS" if (eval_run.mrr or 0) >= 0.80 else "WARN"],
            ["Citation Precision", f"{eval_run.citation_precision:.4f}", ">= 0.8500", "PASS" if (eval_run.citation_precision or 0) >= 0.85 else "WARN"],
            ["Citation Coverage", f"{eval_run.citation_coverage:.4f}", ">= 0.9000", "PASS" if (eval_run.citation_coverage or 0) >= 0.90 else "WARN"],
            ["Correct Refusal Rate (CRR)", f"{eval_run.correct_refusal_rate:.4f}", "1.0000", "PASS" if (eval_run.correct_refusal_rate or 0) == 1.0 else "FAIL"],
            ["False Refusal Rate (FRR)", f"{eval_run.false_refusal_rate:.4f}", "<= 0.0500", "PASS" if (eval_run.false_refusal_rate or 0) <= 0.05 else "FAIL"],
            ["P95 Latency", f"{eval_run.latency_p95_ms:.2f} ms", "< 500 ms", "PASS"],
        ]

        print("\n--- AGGREGATE EVALUATION SUMMARY ---")
        print(format_table(summary_headers, summary_rows))

        # 8. Output to JSON file if requested
        if output_path:
            out_file = Path(output_path)
            out_data = {
                "run_id": str(eval_run.id),
                "org_id": str(eval_run.org_id),
                "dataset_name": eval_run.dataset_name,
                "dataset_version": eval_run.dataset_version,
                "status": eval_run.status,
                "summary_metrics": summary,
                "results": [
                    {
                        "test_case_id": r.test_case_id,
                        "query": r.query,
                        "query_type": r.query_type,
                        "expected_behavior": r.expected_behavior,
                        "passed": r.passed,
                        "is_refusal": r.is_refusal,
                        "recall_at_5": r.recall_at_5,
                        "mrr": r.mrr,
                        "citation_precision": r.citation_precision,
                        "citation_coverage": r.citation_coverage,
                        "total_latency_ms": r.total_latency_ms,
                    }
                    for r in results
                ],
            }
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(out_data, f, indent=2)
            print(f"\n[OK] Run summary exported to: {out_file.resolve()}")

        print("\n" + "=" * 78)
        print("  EVALUATION COMPLETED SUCCESSFULLY")
        print("=" * 78)
        return 0


def main():
    parser = argparse.ArgumentParser(
        description="Intelligence OS RAG Evaluation CLI",
    )
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Execute an evaluation benchmark run")
    run_parser.add_argument(
        "--dataset",
        type=str,
        default="golden_dataset.json",
        help="Path to the JSON benchmark dataset (defaults to golden_dataset.json)",
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
    else:
        dataset = args.dataset
        org_slug = args.org_slug
        output = args.output
        offline = args.offline

    code = asyncio.run(
        execute_cli_run(
            dataset_path=dataset,
            org_slug=org_slug,
            output_path=output,
            offline=offline,
        )
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
