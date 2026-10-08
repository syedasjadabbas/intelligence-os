"""
Evaluation service layer for Intelligence OS RAG evaluation framework.
Enforces strict multi-tenant isolation (org_id scoping), executes bounded
benchmarks synchronously via EvalRunner, and computes run comparisons.
"""

from datetime import datetime
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.eval.judges import DeterministicJudge, LLMJudge
from app.eval.runner import EvalRunner
from app.models.evaluation import EvalRun, EvalRunResult
from app.schemas.evaluation import (
    EvaluationComparisonDeltas,
    EvaluationComparisonResponse,
    EvaluationResultDetail,
    EvaluationResultListItem,
    EvaluationRunCreate,
    EvaluationRunDetail,
    EvaluationRunListItem,
    MetricDelta,
)

logger = logging.getLogger(__name__)

BENCHMARKS_DIR = Path(__file__).resolve().parent.parent / "eval" / "benchmarks"


def _extract_judge_type(run: EvalRun) -> str:
    """Extracts human-readable judge type from config snapshot or models."""
    snapshot = run.config_snapshot or {}
    judge = snapshot.get("judge", "")
    if "LLM" in judge or (run.llm_provider and "gemini" in run.llm_provider.lower()):
        return "llm"
    return "deterministic"


def _compute_pass_rate(passed: int, total: int) -> float:
    """Calculates pass rate safely."""
    if total <= 0:
        return 0.0
    return round(passed / total, 4)


def _to_run_list_item(run: EvalRun) -> EvaluationRunListItem:
    """Maps database EvalRun model to EvaluationRunListItem schema."""
    return EvaluationRunListItem(
        id=run.id,
        org_id=run.org_id,
        dataset_name=run.dataset_name,
        dataset_version=run.dataset_version,
        status=run.status,
        judge_type=_extract_judge_type(run),
        llm_provider=run.llm_provider,
        llm_model=run.llm_model,
        total_test_cases=run.total_test_cases,
        passed_test_cases=run.passed_test_cases,
        pass_rate=_compute_pass_rate(run.passed_test_cases, run.total_test_cases),
        recall_at_3=run.recall_at_3,
        recall_at_5=run.recall_at_5,
        mrr=run.mrr,
        ndcg_at_5=run.ndcg_at_5,
        citation_precision=run.citation_precision,
        citation_coverage=run.citation_coverage,
        mean_faithfulness=run.mean_faithfulness,
        mean_correctness=run.mean_correctness,
        mean_completeness=run.mean_completeness,
        mean_citation_correctness=run.mean_citation_correctness,
        mean_latency_ms=run.mean_latency_ms,
        latency_p95_ms=run.latency_p95_ms,
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
    )


def _to_run_detail(run: EvalRun) -> EvaluationRunDetail:
    """Maps database EvalRun model to EvaluationRunDetail schema."""
    return EvaluationRunDetail(
        id=run.id,
        org_id=run.org_id,
        dataset_name=run.dataset_name,
        dataset_version=run.dataset_version,
        status=run.status,
        judge_type=_extract_judge_type(run),
        llm_provider=run.llm_provider,
        llm_model=run.llm_model,
        embedding_model=run.embedding_model,
        reranker_model=run.reranker_model,
        total_test_cases=run.total_test_cases,
        passed_test_cases=run.passed_test_cases,
        pass_rate=_compute_pass_rate(run.passed_test_cases, run.total_test_cases),
        recall_at_3=run.recall_at_3,
        recall_at_5=run.recall_at_5,
        mrr=run.mrr,
        ndcg_at_5=run.ndcg_at_5,
        citation_precision=run.citation_precision,
        citation_coverage=run.citation_coverage,
        correct_refusal_rate=run.correct_refusal_rate,
        false_refusal_rate=run.false_refusal_rate,
        mean_faithfulness=run.mean_faithfulness,
        mean_correctness=run.mean_correctness,
        mean_completeness=run.mean_completeness,
        mean_citation_correctness=run.mean_citation_correctness,
        mean_latency_ms=run.mean_latency_ms,
        latency_p95_ms=run.latency_p95_ms,
        config_snapshot=run.config_snapshot or {},
        summary_metrics=run.summary_metrics or {},
        regression_summary=run.regression_summary or {},
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
    )


def _calculate_metric_delta(
    base_val: Optional[float],
    target_val: Optional[float],
    higher_is_better: bool = True,
) -> MetricDelta:
    """Computes difference, percentage change, and status for a single metric."""
    if base_val is None and target_val is None:
        return MetricDelta(base_value=None, target_value=None, delta=None, percent_change=None, status="neutral")

    if base_val is None:
        return MetricDelta(base_value=None, target_value=target_val, delta=None, percent_change=None, status="neutral")

    if target_val is None:
        return MetricDelta(base_value=base_val, target_value=None, delta=None, percent_change=None, status="neutral")

    delta = round(target_val - base_val, 4)

    # Safely compute percent change
    if base_val == 0.0:
        pct_change = 0.0 if delta == 0.0 else None
    else:
        pct_change = round((delta / base_val) * 100.0, 2)

    # Determine status (improved, regressed, neutral)
    threshold = 0.001
    if not higher_is_better:
        # For latency, lower is better
        if delta < -threshold:
            status = "improved"
        elif delta > threshold:
            status = "regressed"
        else:
            status = "neutral"
    else:
        # Standard metrics, higher is better
        if delta > threshold:
            status = "improved"
        elif delta < -threshold:
            status = "regressed"
        else:
            status = "neutral"

    return MetricDelta(
        base_value=base_val,
        target_value=target_val,
        delta=delta,
        percent_change=pct_change,
        status=status,
    )


class EvaluationService:
    """Enterprise evaluation service with database-level isolation."""

    @staticmethod
    async def list_runs(
        db: AsyncSession,
        org_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
        judge_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Tuple[List[EvaluationRunListItem], int]:
        """Lists evaluation runs for an organization with pagination and filtering."""
        query = select(EvalRun).where(EvalRun.org_id == org_id)

        if status:
            query = query.where(EvalRun.status == status.upper())

        # Total count query
        count_stmt = select(func.count()).select_from(query.subquery())
        total_res = await db.execute(count_stmt)
        total = total_res.scalar_one()

        # Sorted newest-first with pagination
        stmt = query.order_by(EvalRun.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        runs = result.scalars().all()

        items = [_to_run_list_item(r) for r in runs]

        # Optional in-memory filter if judge_type was requested
        if judge_type:
            requested = judge_type.lower()
            items = [item for item in items if item.judge_type == requested]

        return items, total

    @staticmethod
    async def get_run(
        db: AsyncSession,
        org_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> Optional[EvaluationRunDetail]:
        """Retrieves single evaluation run ensuring multi-tenant isolation."""
        stmt = select(EvalRun).where(EvalRun.id == run_id, EvalRun.org_id == org_id)
        result = await db.execute(stmt)
        run = result.scalar_one_or_none()
        if not run:
            return None
        return _to_run_detail(run)

    @staticmethod
    async def list_results(
        db: AsyncSession,
        org_id: uuid.UUID,
        run_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
        passed: Optional[bool] = None,
        query_type: Optional[str] = None,
        is_refusal: Optional[bool] = None,
    ) -> Optional[Tuple[List[EvaluationResultListItem], int]]:
        """
        Retrieves paginated test case results for an evaluation run.
        Returns None if run does not exist or belongs to another tenant.
        """
        # Verify run exists and belongs to tenant
        run_check = await db.execute(
            select(EvalRun.id).where(EvalRun.id == run_id, EvalRun.org_id == org_id)
        )
        if not run_check.scalar_one_or_none():
            return None

        query = select(EvalRunResult).where(
            EvalRunResult.run_id == run_id,
            EvalRunResult.org_id == org_id,
        )

        if passed is not None:
            query = query.where(EvalRunResult.passed == passed)
        if query_type:
            query = query.where(EvalRunResult.query_type == query_type)
        if is_refusal is not None:
            query = query.where(EvalRunResult.is_refusal == is_refusal)

        # Count total results matching filters
        count_stmt = select(func.count()).select_from(query.subquery())
        total_res = await db.execute(count_stmt)
        total = total_res.scalar_one()

        # Ordered and paginated
        stmt = (
            query.order_by(EvalRunResult.test_case_id.asc())
            .offset(skip)
            .limit(limit)
        )
        res = await db.execute(stmt)
        results = res.scalars().all()

        items = [
            EvaluationResultListItem(
                id=r.id,
                run_id=r.run_id,
                test_case_id=r.test_case_id,
                query=r.query,
                query_type=r.query_type,
                expected_behavior=r.expected_behavior,
                generated_answer=r.generated_answer,
                passed=r.passed,
                is_refusal=r.is_refusal,
                recall_at_3=r.recall_at_3,
                recall_at_5=r.recall_at_5,
                mrr=r.mrr,
                ndcg_at_5=r.ndcg_at_5,
                citation_precision=r.citation_precision,
                citation_coverage=r.citation_coverage,
                faithfulness=r.faithfulness,
                correctness=r.correctness,
                completeness=r.completeness,
                citation_correctness=r.citation_correctness,
                total_latency_ms=r.total_latency_ms,
                failure_reason=r.failure_reason,
                created_at=r.created_at,
            )
            for r in results
        ]

        return items, total

    @staticmethod
    async def get_result(
        db: AsyncSession,
        org_id: uuid.UUID,
        run_id: uuid.UUID,
        result_id: uuid.UUID,
    ) -> Optional[EvaluationResultDetail]:
        """
        Retrieves full case detail inspection for a single benchmark result.
        Returns None if not found, belongs to a different run, or cross-tenant.
        """
        # Explicitly verify the parent evaluation run exists for this tenant
        run_check = await db.execute(
            select(EvalRun.id).where(EvalRun.id == run_id, EvalRun.org_id == org_id)
        )
        if not run_check.scalar_one_or_none():
            return None

        stmt = select(EvalRunResult).where(
            EvalRunResult.id == result_id,
            EvalRunResult.run_id == run_id,
            EvalRunResult.org_id == org_id,
        )
        res = await db.execute(stmt)
        r = res.scalar_one_or_none()
        if not r:
            return None

        return EvaluationResultDetail(
            id=r.id,
            run_id=r.run_id,
            org_id=r.org_id,
            test_case_id=r.test_case_id,
            query=r.query,
            query_type=r.query_type,
            expected_behavior=r.expected_behavior,
            generated_answer=r.generated_answer,
            passed=r.passed,
            is_refusal=r.is_refusal,
            recall_at_3=r.recall_at_3,
            recall_at_5=r.recall_at_5,
            mrr=r.mrr,
            ndcg_at_5=r.ndcg_at_5,
            citation_precision=r.citation_precision,
            citation_coverage=r.citation_coverage,
            faithfulness=r.faithfulness,
            correctness=r.correctness,
            completeness=r.completeness,
            citation_correctness=r.citation_correctness,
            total_latency_ms=r.total_latency_ms,
            retrieved_candidates=r.retrieved_candidates or [],
            reranked_candidates=r.reranked_candidates or [],
            citations=r.citations or [],
            trace_data=r.trace_data or {},
            judge_output=r.judge_output or {},
            failure_reason=r.failure_reason,
            created_at=r.created_at,
        )

    @staticmethod
    async def start_evaluation_run(
        db: AsyncSession,
        org_id: uuid.UUID,
        payload: EvaluationRunCreate,
    ) -> EvaluationRunDetail:
        """
        Synchronously and boundedly executes an evaluation run for an organization.
        Enforces hard server-side limit cap of MAX_EVAL_CASES (50).
        No Redis/Celery queue required.
        """
        MAX_EVAL_CASES = 50
        requested_limit = payload.limit if payload.limit is not None else MAX_EVAL_CASES
        bounded_limit = max(1, min(requested_limit, MAX_EVAL_CASES))

        dataset_path = BENCHMARKS_DIR / f"{payload.dataset_name}.json"
        if not dataset_path.exists():
            # Fallback to golden_dataset.json if named differently
            dataset_path = BENCHMARKS_DIR / "golden_dataset.json"

        judge_mode = payload.judge_type.strip().lower()
        if judge_mode == "llm":
            judge = LLMJudge()
            offline = False
        else:
            judge = DeterministicJudge()
            offline = payload.offline

        runner = EvalRunner(
            db=db,
            org_id=org_id,
            judge=judge,
            offline=offline,
        )

        logger.info(
            f"Executing evaluation run for org {org_id} (dataset: {payload.dataset_name}, "
            f"judge: {judge_mode}, bounded_limit: {bounded_limit})"
        )

        run_model = await runner.run_benchmark(
            dataset_input=dataset_path,
            run_name=f"api-run-{int(datetime.now().timestamp())}",
            limit=bounded_limit,
        )

        return _to_run_detail(run_model)

    @staticmethod
    async def compare_runs(
        db: AsyncSession,
        org_id: uuid.UUID,
        base_run_id: uuid.UUID,
        target_run_id: uuid.UUID,
    ) -> Optional[EvaluationComparisonResponse]:
        """
        Compares two evaluation runs for the same organization and computes metric deltas.
        Returns None if either run does not exist or does not belong to the organization.
        """
        # Fetch base run
        base_stmt = select(EvalRun).where(EvalRun.id == base_run_id, EvalRun.org_id == org_id)
        base_res = await db.execute(base_stmt)
        base_run = base_res.scalar_one_or_none()

        # Fetch target run
        target_stmt = select(EvalRun).where(EvalRun.id == target_run_id, EvalRun.org_id == org_id)
        target_res = await db.execute(target_stmt)
        target_run = target_res.scalar_one_or_none()

        if not base_run or not target_run:
            return None

        base_pass_rate = _compute_pass_rate(base_run.passed_test_cases, base_run.total_test_cases)
        target_pass_rate = _compute_pass_rate(target_run.passed_test_cases, target_run.total_test_cases)

        deltas = EvaluationComparisonDeltas(
            pass_rate=_calculate_metric_delta(base_pass_rate, target_pass_rate, higher_is_better=True),
            recall_at_3=_calculate_metric_delta(base_run.recall_at_3, target_run.recall_at_3, higher_is_better=True),
            recall_at_5=_calculate_metric_delta(base_run.recall_at_5, target_run.recall_at_5, higher_is_better=True),
            mrr=_calculate_metric_delta(base_run.mrr, target_run.mrr, higher_is_better=True),
            ndcg_at_5=_calculate_metric_delta(base_run.ndcg_at_5, target_run.ndcg_at_5, higher_is_better=True),
            citation_precision=_calculate_metric_delta(base_run.citation_precision, target_run.citation_precision, higher_is_better=True),
            citation_coverage=_calculate_metric_delta(base_run.citation_coverage, target_run.citation_coverage, higher_is_better=True),
            mean_faithfulness=_calculate_metric_delta(base_run.mean_faithfulness, target_run.mean_faithfulness, higher_is_better=True),
            mean_correctness=_calculate_metric_delta(base_run.mean_correctness, target_run.mean_correctness, higher_is_better=True),
            mean_completeness=_calculate_metric_delta(base_run.mean_completeness, target_run.mean_completeness, higher_is_better=True),
            mean_citation_correctness=_calculate_metric_delta(base_run.mean_citation_correctness, target_run.mean_citation_correctness, higher_is_better=True),
            mean_latency_ms=_calculate_metric_delta(base_run.mean_latency_ms, target_run.mean_latency_ms, higher_is_better=False),
        )

        # Calculate case-level regression and improvement
        base_cases_stmt = select(EvalRunResult.test_case_id, EvalRunResult.passed).where(
            EvalRunResult.run_id == base_run_id, EvalRunResult.org_id == org_id
        )
        target_cases_stmt = select(EvalRunResult.test_case_id, EvalRunResult.passed).where(
            EvalRunResult.run_id == target_run_id, EvalRunResult.org_id == org_id
        )

        base_cases = dict((await db.execute(base_cases_stmt)).all())
        target_cases = dict((await db.execute(target_cases_stmt)).all())

        regressed_cases_count = 0
        improved_cases_count = 0

        for tc_id, base_passed in base_cases.items():
            if tc_id in target_cases:
                target_passed = target_cases[tc_id]
                if base_passed and not target_passed:
                    regressed_cases_count += 1
                elif not base_passed and target_passed:
                    improved_cases_count += 1

        return EvaluationComparisonResponse(
            base_run=_to_run_list_item(base_run),
            target_run=_to_run_list_item(target_run),
            deltas=deltas,
            regressed_cases_count=regressed_cases_count,
            improved_cases_count=improved_cases_count,
        )


evaluation_service = EvaluationService()
