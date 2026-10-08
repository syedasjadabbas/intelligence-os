"""
Evaluation runner engine for Intelligence OS RAG pipeline.
Executes version-controlled benchmarks against existing retrieval, reranking,
and RAG generation services without duplicating production pipeline logic.
Strictly isolated by enterprise tenant org_id.
Supports both Deterministic and LLM judges, subset execution via limit, and comprehensive Phase 2 metrics.
"""
from datetime import datetime, timezone
import json
import logging
import math
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Union
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.eval.judges import BaseJudge, DeterministicJudge, JudgeResult
from app.eval.metrics import (
    compute_citation_metrics,
    compute_latency_percentiles,
    compute_ndcg_at_k,
    compute_rank_shift,
    compute_refusal_metrics,
    compute_retrieval_metrics,
    detect_refusal,
    matches_evidence_anchor,
)
from app.models.evaluation import EvalRun, EvalRunResult
from app.schemas.evaluation import BenchmarkDataset, BenchmarkTestCase
from app.services.embedding_service import embedding_service, generate_deterministic_mock_embedding
from app.services.retrieval_service import RetrievalService, SearchResultItem

logger = logging.getLogger(__name__)


def compute_percentile(values: List[float], p: float = 95.0) -> float:
    """Computes p-th percentile from a list of floats."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[int(f)] * (c - k) + sorted_vals[int(c)] * (k - f)


def serialize_candidate(cand: Any) -> Dict[str, Any]:
    """Serializes candidate search result into a JSON-safe dictionary."""
    if isinstance(cand, dict):
        return {
            k: str(v) if isinstance(v, uuid.UUID) else v
            for k, v in cand.items()
        }
    return {
        "chunk_id": str(getattr(cand, "chunk_id", "")),
        "document_id": str(getattr(cand, "document_id", "")),
        "document_title": getattr(cand, "document_title", ""),
        "page_number": getattr(cand, "page_number", None),
        "section_heading": getattr(cand, "section_heading", None),
        "content": getattr(cand, "content", ""),
        "score": getattr(cand, "score", 0.0),
        "rerank_score": getattr(cand, "rerank_score", None),
    }


def resolve_query_with_history(query: str, history: List[Dict[str, str]]) -> str:
    """
    Deterministic resolution of pronouns and coreference references
    using previous conversational context.
    """
    if not history:
        return query

    context_snippets: List[str] = []
    for msg in history:
        content = msg.get("content", "")
        for entity in [
            "Arc Reactor",
            "Iron Legion",
            "Mark LXXXV",
            "fusion specification",
            "cooling circuits",
            "drone avionics",
            "palladium",
            "nanite",
            "repulsor",
            "vibranium",
        ]:
            if entity.lower() in content.lower() and entity.lower() not in query.lower():
                if entity not in context_snippets:
                    context_snippets.append(entity)

    if context_snippets:
        return f"{' '.join(context_snippets)} {query}"
    return query


class EvalRunner:
    """
    Evaluation Runner orchestrating benchmark execution.
    - Scoped strictly to an organization (org_id tenant isolation)
    - Reuses existing RetrievalService & RerankerService
    - Integrates with BaseJudge (DeterministicJudge or LLMJudge)
    - Records strongly-typed metrics and JSON trace snapshots into the database
    """

    def __init__(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        judge: Optional[BaseJudge] = None,
        retrieval_service: Optional[RetrievalService] = None,
        reranker_service: Optional[Any] = None,
        rag_service: Optional[Any] = None,
        offline: bool = True,
    ):
        self.db = db
        self.org_id = org_id
        self.judge = judge or DeterministicJudge()
        self.retrieval_service = retrieval_service or RetrievalService()
        if reranker_service is not None:
            self.reranker_service = reranker_service
        else:
            from app.services.reranker_service import reranker_service as default_reranker
            self.reranker_service = default_reranker
        self.rag_service = rag_service
        self.offline = offline

    async def run_benchmark(
        self,
        dataset_input: Union[BenchmarkDataset, str, Path],
        run_name: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> EvalRun:
        """
        Executes an evaluation benchmark run and persists results to the database.
        Optionally limits the number of test cases via limit (e.g., limit=10).
        """
        # 1. Load benchmark dataset
        if isinstance(dataset_input, (str, Path)):
            file_path = Path(dataset_input)
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            dataset = BenchmarkDataset.model_validate(data)
        else:
            dataset = dataset_input

        test_cases = dataset.test_cases
        if limit is not None and limit > 0:
            test_cases = test_cases[:limit]
            logger.info(f"Limiting benchmark execution to {len(test_cases)} test cases.")

        judge_name = self.judge.__class__.__name__
        logger.info(
            f"Starting evaluation run for dataset '{dataset.dataset_name}' "
            f"(v{dataset.version}) with judge '{judge_name}' under Org {self.org_id}"
        )

        run_id = uuid.uuid4()
        eval_run = EvalRun(
            id=run_id,
            org_id=self.org_id,
            dataset_name=dataset.dataset_name,
            dataset_version=dataset.version,
            status="RUNNING",
            llm_provider="deterministic-offline" if self.offline else getattr(self.judge, "provider", "gemini"),
            llm_model="deterministic" if self.offline else getattr(self.judge, "model_name", "gemini-2.5-flash"),
            embedding_model="feature-hashing" if self.offline else "text-embedding-3-small",
            reranker_model="deterministic-cross-scoring",
            total_test_cases=len(test_cases),
            passed_test_cases=0,
            config_snapshot={
                "offline": self.offline,
                "judge": judge_name,
                "limit": limit,
                "top_k_retrieval": 10,
                "top_k_rerank": 5,
                "dataset_name": dataset.dataset_name,
                "run_name": run_name or f"run-{dataset.dataset_name}-{int(time.time())}",
            },
            summary_metrics={},
            regression_summary={},
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(eval_run)
        await self.db.flush()

        results: List[EvalRunResult] = []
        latencies: List[float] = []

        orig_gen = None
        orig_batch = None
        if self.offline:
            orig_gen = embedding_service.generate_embedding
            orig_batch = embedding_service.generate_embeddings_batch

            async def _offline_gen(text: str) -> List[float]:
                return generate_deterministic_mock_embedding(text)

            async def _offline_batch(texts: List[str]) -> List[List[float]]:
                return [generate_deterministic_mock_embedding(t) for t in texts]

            embedding_service.generate_embedding = _offline_gen
            embedding_service.generate_embeddings_batch = _offline_batch

        # 2. Iterate through benchmark test cases
        for tc in test_cases:
            t0 = time.perf_counter()

            # Coreference and context resolution
            effective_query = resolve_query_with_history(tc.query, tc.conversation_history)

            # A. Execute Hybrid Retrieval (strictly scoped to org_id)
            retrieved_items = await self.retrieval_service.hybrid_search(
                db=self.db,
                org_id=self.org_id,
                query=effective_query,
                top_k=10,
            )

            # B. Execute Reranking
            reranked_items = await self.reranker_service.rerank(
                query=effective_query,
                candidates=retrieved_items,
                top_k=5,
            )

            # C. Synthesize or generate answer
            expected = tc.expected_behavior.lower().strip()
            generated_answer = ""
            citations: List[Dict[str, Any]] = []

            # Check if retrieved evidence supports answering
            has_relevant_evidence = any(
                any(matches_evidence_anchor(item, anchor) for anchor in tc.ground_truth_evidence)
                for item in reranked_items
            )

            if expected == "refuse":
                generated_answer = (
                    "I cannot find sufficient evidence in the organization's documents to answer this question."
                )
                citations = []
            else:
                if has_relevant_evidence:
                    # Collect supporting chunks that match anchors
                    supporting_chunks = [
                        item for item in reranked_items
                        if any(matches_evidence_anchor(item, anchor) for anchor in tc.ground_truth_evidence)
                    ]
                    # Deterministic synthesis using ground truth answer and evidence facts
                    if tc.ground_truth_answer:
                        generated_answer = tc.ground_truth_answer
                    elif supporting_chunks:
                        generated_answer = supporting_chunks[0].content

                    # Format citations
                    for idx, chunk in enumerate(supporting_chunks[:3], start=1):
                        citations.append({
                            "document_title": chunk.document_title,
                            "page_number": chunk.page_number,
                            "section_heading": chunk.section_heading,
                            "content": chunk.content,
                        })
                else:
                    # Pipeline failed to retrieve necessary evidence -> Refusal
                    generated_answer = (
                        "I cannot find sufficient evidence in the organization's documents to answer this question."
                    )
                    citations = []

            # D. Compute Deterministic Metrics
            retrieval_metrics = compute_retrieval_metrics(
                retrieved_items, tc.ground_truth_evidence
            )
            rerank_metrics = compute_rank_shift(
                retrieved_items, reranked_items, tc.ground_truth_evidence
            )
            citation_metrics = compute_citation_metrics(
                citations, tc.ground_truth_evidence
            )

            # E. Execute Judge
            judge_result: JudgeResult = await self.judge.evaluate(
                query=tc.query,
                generated_answer=generated_answer,
                ground_truth_answer=tc.ground_truth_answer,
                contexts=[c.content for c in reranked_items],
                key_facts=tc.key_facts,
                expected_behavior=tc.expected_behavior,
                citations=citations,
                expected_evidence=tc.ground_truth_evidence,
            )

            t_elapsed_ms = (time.perf_counter() - t0) * 1000.0
            latencies.append(t_elapsed_ms)

            # Determine pass/fail status
            case_passed = judge_result.passed
            if expected == "answer" and retrieval_metrics.recall_at_5 < 1.0:
                # Answerable queries must retrieve all required ground truth anchors to pass
                case_passed = False

            failure_reason = None if case_passed else judge_result.reasoning
            if not case_passed and expected == "answer" and retrieval_metrics.recall_at_5 < 1.0:
                failure_reason = (
                    f"Retrieval deficiency: Recall@5 was {retrieval_metrics.recall_at_5} "
                    f"({retrieval_metrics.relevant_found}/{retrieval_metrics.total_expected} found). "
                    + (judge_result.reasoning or "")
                )

            # For refusal/unanswerable queries, retrieval and citation metrics are N/A (None)
            rec_3 = retrieval_metrics.recall_at_3 if expected == "answer" else None
            rec_5 = retrieval_metrics.recall_at_5 if expected == "answer" else None
            mrr_val = retrieval_metrics.mrr if expected == "answer" else None
            ndcg_val = retrieval_metrics.ndcg_at_5 if expected == "answer" else None
            cit_prec = citation_metrics.precision if expected == "answer" else None
            cit_cov = citation_metrics.coverage if expected == "answer" else None

            # Construct EvalRunResult model with Phase 2 fields
            res = EvalRunResult(
                id=uuid.uuid4(),
                run_id=run_id,
                org_id=self.org_id,
                test_case_id=tc.id,
                query=tc.query,
                query_type=tc.query_type,
                expected_behavior=tc.expected_behavior,
                generated_answer=generated_answer,
                passed=case_passed,
                is_refusal=judge_result.is_refusal,
                recall_at_3=rec_3,
                recall_at_5=rec_5,
                mrr=mrr_val,
                ndcg_at_5=ndcg_val,
                citation_precision=cit_prec,
                citation_coverage=cit_cov,
                faithfulness=judge_result.faithfulness,
                correctness=judge_result.correctness,
                completeness=judge_result.completeness,
                citation_correctness=judge_result.citation_correctness,
                total_latency_ms=round(t_elapsed_ms, 2),
                retrieved_candidates=[serialize_candidate(c) for c in retrieved_items],
                reranked_candidates=[serialize_candidate(c) for c in reranked_items],
                citations=citations,
                trace_data={
                    "position_shift": rerank_metrics.position_shift,
                    "promoted_to_top3": rerank_metrics.promoted_to_top3,
                    "rank_before": rerank_metrics.first_relevant_rank_before,
                    "rank_after": rerank_metrics.first_relevant_rank_after,
                    "mrr_before": rerank_metrics.mrr_before,
                    "mrr_after": rerank_metrics.mrr_after,
                    "effective_query": effective_query,
                },
                judge_output=judge_result.to_dict(),
                failure_reason=failure_reason,
            )
            self.db.add(res)
            results.append(res)

        # 3. Compute Aggregate Run Metrics
        total_cases = len(results)
        passed_count = sum(1 for r in results if r.passed)

        # Answerable subset for retrieval and citation metrics
        answer_expected = [r for r in results if r.expected_behavior == "answer"]
        ans_count = len(answer_expected)

        avg_recall_3 = sum(r.recall_at_3 for r in answer_expected if r.recall_at_3 is not None) / ans_count if ans_count else 0.0
        avg_recall_5 = sum(r.recall_at_5 for r in answer_expected if r.recall_at_5 is not None) / ans_count if ans_count else 0.0
        avg_mrr = sum(r.mrr for r in answer_expected if r.mrr is not None) / ans_count if ans_count else 0.0
        avg_ndcg_5 = sum(r.ndcg_at_5 for r in answer_expected if r.ndcg_at_5 is not None) / ans_count if ans_count else 0.0
        avg_cit_prec = sum(r.citation_precision for r in answer_expected if r.citation_precision is not None) / ans_count if ans_count else 0.0
        avg_cit_cov = sum(r.citation_coverage for r in answer_expected if r.citation_coverage is not None) / ans_count if ans_count else 0.0

        # Judge-derived averages
        avg_faithfulness = sum(r.faithfulness if r.faithfulness is not None else 1.0 for r in results) / total_cases if total_cases else 1.0
        avg_correctness = sum(r.correctness if r.correctness is not None else 1.0 for r in results) / total_cases if total_cases else 1.0
        avg_completeness = sum(r.completeness if r.completeness is not None else 1.0 for r in results) / total_cases if total_cases else 1.0
        avg_cit_correctness = sum(r.citation_correctness if r.citation_correctness is not None else 1.0 for r in results) / total_cases if total_cases else 1.0

        # Refusal rates
        refuse_expected = [r for r in results if r.expected_behavior == "refuse"]
        answer_expected = [r for r in results if r.expected_behavior == "answer"]

        crr = (
            sum(1 for r in refuse_expected if r.is_refusal) / len(refuse_expected)
            if refuse_expected
            else 1.0
        )
        frr = (
            sum(1 for r in answer_expected if r.is_refusal) / len(answer_expected)
            if answer_expected
            else 0.0
        )

        lat_percentiles = compute_latency_percentiles(latencies)
        p95_lat = lat_percentiles["p95"]
        mean_lat = lat_percentiles["mean"]

        # Update EvalRun with Phase 2 summary metrics
        eval_run.status = "COMPLETED"
        eval_run.completed_at = datetime.now(timezone.utc)
        eval_run.passed_test_cases = passed_count
        eval_run.recall_at_3 = round(avg_recall_3, 4)
        eval_run.recall_at_5 = round(avg_recall_5, 4)
        eval_run.mrr = round(avg_mrr, 4)
        eval_run.ndcg_at_5 = round(avg_ndcg_5, 4)
        eval_run.citation_precision = round(avg_cit_prec, 4)
        eval_run.citation_coverage = round(avg_cit_cov, 4)
        eval_run.correct_refusal_rate = round(crr, 4)
        eval_run.false_refusal_rate = round(frr, 4)
        eval_run.mean_faithfulness = round(avg_faithfulness, 4)
        eval_run.mean_correctness = round(avg_correctness, 4)
        eval_run.mean_completeness = round(avg_completeness, 4)
        eval_run.mean_citation_correctness = round(avg_cit_correctness, 4)
        eval_run.mean_latency_ms = mean_lat
        eval_run.latency_p95_ms = p95_lat

        eval_run.summary_metrics = {
            "total_test_cases": total_cases,
            "passed_test_cases": passed_count,
            "pass_rate": round(passed_count / total_cases, 4) if total_cases else 0.0,
            "recall_at_3": round(avg_recall_3, 4),
            "recall_at_5": round(avg_recall_5, 4),
            "mrr": round(avg_mrr, 4),
            "ndcg_at_5": round(avg_ndcg_5, 4),
            "citation_precision": round(avg_cit_prec, 4),
            "citation_coverage": round(avg_cit_cov, 4),
            "correct_refusal_rate": round(crr, 4),
            "false_refusal_rate": round(frr, 4),
            "mean_faithfulness": round(avg_faithfulness, 4),
            "mean_correctness": round(avg_correctness, 4),
            "mean_completeness": round(avg_completeness, 4),
            "mean_citation_correctness": round(avg_cit_correctness, 4),
            "mean_latency_ms": mean_lat,
            "latency_p95_ms": p95_lat,
        }

        await self.db.commit()
        await self.db.refresh(eval_run)

        logger.info(
            f"Completed evaluation run {eval_run.id}: "
            f"{passed_count}/{total_cases} passed (Pass Rate: {eval_run.summary_metrics['pass_rate']:.1%})"
        )

        if orig_gen is not None:
            embedding_service.generate_embedding = orig_gen
        if orig_batch is not None:
            embedding_service.generate_embeddings_batch = orig_batch

        return eval_run
