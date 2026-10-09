"""
Evaluation service layer for Intelligence OS RAG evaluation framework.
Enforces strict multi-tenant isolation (org_id scoping), executes bounded
benchmarks synchronously via EvalRunner, and computes run comparisons.
"""

from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.eval.judges import DeterministicJudge, LLMJudge
from app.eval.runner import EvalRunner
from app.models.evaluation import EvalDataset, EvalRun, EvalRunResult, EvalTestCase
from app.schemas.evaluation import (
    BenchmarkDataset,
    BenchmarkTestCase,
    DatasetCreate,
    DatasetDetail,
    DatasetListItem,
    DatasetUpdate,
    DatasetsPage,
    EvidenceAnchor,
    EvaluationComparisonDeltas,
    EvaluationComparisonResponse,
    EvaluationResultDetail,
    EvaluationResultListItem,
    EvaluationRunCreate,
    EvaluationRunDetail,
    EvaluationRunListItem,
    MetricDelta,
    TestCaseCreate,
    TestCaseDetail,
    TestCaseUpdate,
)

logger = logging.getLogger(__name__)

BENCHMARKS_DIR = Path(__file__).resolve().parent.parent / "eval" / "benchmarks"

# In-memory tracking of currently executing/pending evaluation run IDs in this process.
# Prevents false positive failure marking of active runs during orphaned run recovery checks.
_active_run_ids: set[uuid.UUID] = set()


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
        dataset_id=getattr(run, "dataset_id", None),
        dataset_name=run.dataset_name,
        dataset_version=run.dataset_version,
        status=run.status,
        judge_type=_extract_judge_type(run),
        llm_provider=run.llm_provider,
        llm_model=run.llm_model,
        total_test_cases=run.total_test_cases,
        passed_test_cases=run.passed_test_cases,
        pass_rate=_compute_pass_rate(run.passed_test_cases, run.total_test_cases),
        progress_current=getattr(run, "progress_current", 0) or 0,
        progress_total=getattr(run, "progress_total", 0) or 0,
        error_message=getattr(run, "error_message", None),
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
        dataset_id=getattr(run, "dataset_id", None),
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
        progress_current=getattr(run, "progress_current", 0) or 0,
        progress_total=getattr(run, "progress_total", 0) or 0,
        error_message=getattr(run, "error_message", None),
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


def _to_test_case_detail(tc: EvalTestCase) -> TestCaseDetail:
    """Maps database EvalTestCase model to TestCaseDetail schema."""
    evidence_anchors: List[EvidenceAnchor] = []
    for anchor in tc.ground_truth_evidence or []:
        try:
            evidence_anchors.append(EvidenceAnchor.model_validate(anchor))
        except Exception:
            pass
    return TestCaseDetail(
        id=tc.id,
        dataset_id=tc.dataset_id,
        org_id=tc.org_id,
        case_identifier=tc.case_identifier,
        query=tc.query,
        query_type=tc.query_type,
        expected_behavior=tc.expected_behavior,
        ground_truth_answer=tc.ground_truth_answer,
        key_facts=tc.key_facts or [],
        ground_truth_evidence=evidence_anchors,
        conversation_history=tc.conversation_history or [],
        metadata_json=tc.metadata_json or {},
        created_at=tc.created_at,
        updated_at=tc.updated_at,
    )


def _to_dataset_detail(dataset: EvalDataset, cases: List[EvalTestCase]) -> DatasetDetail:
    """Maps database EvalDataset model and its test cases to DatasetDetail schema."""
    return DatasetDetail(
        id=dataset.id,
        org_id=dataset.org_id,
        name=dataset.name,
        description=dataset.description,
        version=dataset.version,
        test_case_count=len(cases),
        test_cases=[_to_test_case_detail(c) for c in cases],
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
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
    async def list_datasets(
        db: AsyncSession,
        org_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[DatasetListItem], int]:
        """Lists all custom evaluation datasets belonging to an organization."""
        count_stmt = select(func.count(EvalDataset.id)).where(EvalDataset.org_id == org_id)
        total_res = await db.execute(count_stmt)
        total = total_res.scalar_one()

        stmt = (
            select(EvalDataset, func.count(EvalTestCase.id).label("tc_count"))
            .outerjoin(EvalTestCase, EvalTestCase.dataset_id == EvalDataset.id)
            .where(EvalDataset.org_id == org_id)
            .group_by(EvalDataset.id)
            .order_by(EvalDataset.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        res = await db.execute(stmt)
        rows = res.all()

        items = [
            DatasetListItem(
                id=d.id,
                org_id=d.org_id,
                name=d.name,
                description=d.description,
                version=d.version,
                test_case_count=tc_count,
                created_at=d.created_at,
                updated_at=d.updated_at,
            )
            for d, tc_count in rows
        ]
        return items, total

    @staticmethod
    async def get_dataset(
        db: AsyncSession,
        org_id: uuid.UUID,
        dataset_id: uuid.UUID,
    ) -> Optional[DatasetDetail]:
        """Retrieves a dataset with all its test cases, strictly tenant-scoped."""
        stmt = select(EvalDataset).where(EvalDataset.id == dataset_id, EvalDataset.org_id == org_id)
        res = await db.execute(stmt)
        dataset = res.scalar_one_or_none()
        if not dataset:
            return None

        cases_stmt = (
            select(EvalTestCase)
            .where(EvalTestCase.dataset_id == dataset_id, EvalTestCase.org_id == org_id)
            .order_by(EvalTestCase.created_at.asc())
        )
        cases_res = await db.execute(cases_stmt)
        cases = cases_res.scalars().all()

        return _to_dataset_detail(dataset, cases)

    @staticmethod
    async def create_dataset(
        db: AsyncSession,
        org_id: uuid.UUID,
        payload: DatasetCreate,
    ) -> DatasetDetail:
        """Creates a new evaluation dataset and optional initial test cases for an organization."""
        clean_name = payload.name.strip()
        existing = await db.execute(
            select(EvalDataset.id).where(EvalDataset.org_id == org_id, EvalDataset.name == clean_name)
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"A dataset named '{clean_name}' already exists.")

        dataset_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        dataset = EvalDataset(
            id=dataset_id,
            org_id=org_id,
            name=clean_name,
            description=payload.description.strip() if payload.description else None,
            version=payload.version.strip() if payload.version else "1.0.0",
            created_at=now,
            updated_at=now,
        )
        db.add(dataset)

        created_cases: List[EvalTestCase] = []
        for idx, tc in enumerate(payload.test_cases):
            cid = tc.case_identifier.strip() if tc.case_identifier else f"TC-{idx+1:03d}"
            ev_list = [e.model_dump() for e in tc.ground_truth_evidence]
            test_case = EvalTestCase(
                id=uuid.uuid4(),
                dataset_id=dataset_id,
                org_id=org_id,
                case_identifier=cid,
                query=tc.query.strip(),
                query_type=tc.query_type,
                expected_behavior=tc.expected_behavior,
                ground_truth_answer=tc.ground_truth_answer,
                key_facts=tc.key_facts,
                ground_truth_evidence=ev_list,
                conversation_history=tc.conversation_history,
                metadata_json=tc.metadata,
                created_at=now,
                updated_at=now,
            )
            db.add(test_case)
            created_cases.append(test_case)

        await db.commit()
        await db.refresh(dataset)
        return _to_dataset_detail(dataset, created_cases)

    @staticmethod
    async def update_dataset(
        db: AsyncSession,
        org_id: uuid.UUID,
        dataset_id: uuid.UUID,
        payload: DatasetUpdate,
    ) -> Optional[DatasetDetail]:
        """Updates dataset metadata (name, description, version)."""
        stmt = select(EvalDataset).where(EvalDataset.id == dataset_id, EvalDataset.org_id == org_id)
        res = await db.execute(stmt)
        dataset = res.scalar_one_or_none()
        if not dataset:
            return None

        if payload.name is not None:
            clean_name = payload.name.strip()
            if clean_name != dataset.name:
                collision = await db.execute(
                    select(EvalDataset.id).where(
                        EvalDataset.org_id == org_id,
                        EvalDataset.name == clean_name,
                        EvalDataset.id != dataset_id,
                    )
                )
                if collision.scalar_one_or_none():
                    raise ValueError(f"A dataset named '{clean_name}' already exists.")
                dataset.name = clean_name

        if payload.description is not None:
            dataset.description = payload.description.strip() if payload.description else None

        if payload.version is not None:
            dataset.version = payload.version.strip() if payload.version else "1.0.0"

        dataset.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(dataset)

        cases_stmt = (
            select(EvalTestCase)
            .where(EvalTestCase.dataset_id == dataset_id, EvalTestCase.org_id == org_id)
            .order_by(EvalTestCase.created_at.asc())
        )
        cases_res = await db.execute(cases_stmt)
        cases = cases_res.scalars().all()
        return _to_dataset_detail(dataset, cases)

    @staticmethod
    async def delete_dataset(
        db: AsyncSession,
        org_id: uuid.UUID,
        dataset_id: uuid.UUID,
    ) -> bool:
        """Deletes a dataset and all associated test cases (cascade)."""
        stmt = select(EvalDataset).where(EvalDataset.id == dataset_id, EvalDataset.org_id == org_id)
        res = await db.execute(stmt)
        dataset = res.scalar_one_or_none()
        if not dataset:
            return False

        await db.delete(dataset)
        await db.commit()
        return True

    @staticmethod
    async def add_test_case(
        db: AsyncSession,
        org_id: uuid.UUID,
        dataset_id: uuid.UUID,
        payload: TestCaseCreate,
    ) -> Optional[TestCaseDetail]:
        """Adds a single test case to an existing dataset."""
        dataset_check = await db.execute(
            select(EvalDataset.id).where(EvalDataset.id == dataset_id, EvalDataset.org_id == org_id)
        )
        if not dataset_check.scalar_one_or_none():
            return None

        count_res = await db.execute(
            select(func.count(EvalTestCase.id)).where(
                EvalTestCase.dataset_id == dataset_id, EvalTestCase.org_id == org_id
            )
        )
        count = count_res.scalar_one()

        cid = payload.case_identifier.strip() if payload.case_identifier else f"TC-{count+1:03d}"
        ev_list = [e.model_dump() for e in payload.ground_truth_evidence]
        now = datetime.now(timezone.utc)
        test_case = EvalTestCase(
            id=uuid.uuid4(),
            dataset_id=dataset_id,
            org_id=org_id,
            case_identifier=cid,
            query=payload.query.strip(),
            query_type=payload.query_type,
            expected_behavior=payload.expected_behavior,
            ground_truth_answer=payload.ground_truth_answer,
            key_facts=payload.key_facts,
            ground_truth_evidence=ev_list,
            conversation_history=payload.conversation_history,
            metadata_json=payload.metadata,
            created_at=now,
            updated_at=now,
        )
        db.add(test_case)

        # Update parent dataset timestamp
        await db.execute(
            update(EvalDataset).where(EvalDataset.id == dataset_id).values(updated_at=now)
        )
        await db.commit()
        await db.refresh(test_case)
        return _to_test_case_detail(test_case)

    @staticmethod
    async def update_test_case(
        db: AsyncSession,
        org_id: uuid.UUID,
        dataset_id: uuid.UUID,
        case_id: uuid.UUID,
        payload: TestCaseUpdate,
    ) -> Optional[TestCaseDetail]:
        """Updates an existing test case in a dataset."""
        stmt = select(EvalTestCase).where(
            EvalTestCase.id == case_id,
            EvalTestCase.dataset_id == dataset_id,
            EvalTestCase.org_id == org_id,
        )
        res = await db.execute(stmt)
        tc = res.scalar_one_or_none()
        if not tc:
            return None

        if payload.case_identifier is not None:
            tc.case_identifier = payload.case_identifier.strip()
        if payload.query is not None:
            tc.query = payload.query.strip()
        if payload.query_type is not None:
            tc.query_type = payload.query_type
        if payload.expected_behavior is not None:
            tc.expected_behavior = payload.expected_behavior
        if payload.ground_truth_answer is not None:
            tc.ground_truth_answer = payload.ground_truth_answer
        if payload.key_facts is not None:
            tc.key_facts = payload.key_facts
        if payload.ground_truth_evidence is not None:
            tc.ground_truth_evidence = [e.model_dump() for e in payload.ground_truth_evidence]
        if payload.conversation_history is not None:
            tc.conversation_history = payload.conversation_history
        if payload.metadata is not None:
            tc.metadata_json = payload.metadata

        now = datetime.now(timezone.utc)
        tc.updated_at = now
        await db.execute(
            update(EvalDataset).where(EvalDataset.id == dataset_id).values(updated_at=now)
        )
        await db.commit()
        await db.refresh(tc)
        return _to_test_case_detail(tc)

    @staticmethod
    async def delete_test_case(
        db: AsyncSession,
        org_id: uuid.UUID,
        dataset_id: uuid.UUID,
        case_id: uuid.UUID,
    ) -> bool:
        """Deletes a test case from a dataset."""
        stmt = select(EvalTestCase).where(
            EvalTestCase.id == case_id,
            EvalTestCase.dataset_id == dataset_id,
            EvalTestCase.org_id == org_id,
        )
        res = await db.execute(stmt)
        tc = res.scalar_one_or_none()
        if not tc:
            return False

        await db.delete(tc)
        now = datetime.now(timezone.utc)
        await db.execute(
            update(EvalDataset).where(EvalDataset.id == dataset_id).values(updated_at=now)
        )
        await db.commit()
        return True

    @staticmethod
    async def load_benchmark_dataset(
        db: AsyncSession,
        org_id: uuid.UUID,
        dataset_name: str,
        dataset_id: Optional[uuid.UUID] = None,
    ) -> BenchmarkDataset:
        """
        Loads a BenchmarkDataset specification either from database-backed test cases
        or from the built-in golden benchmark JSON file.
        """
        import json

        if dataset_id is not None:
            stmt = select(EvalDataset).where(EvalDataset.id == dataset_id, EvalDataset.org_id == org_id)
            res = await db.execute(stmt)
            ds = res.scalar_one_or_none()
            if not ds:
                raise ValueError(f"Dataset {dataset_id} was not found for this organization.")

            cases_stmt = (
                select(EvalTestCase)
                .where(EvalTestCase.dataset_id == dataset_id, EvalTestCase.org_id == org_id)
                .order_by(EvalTestCase.created_at.asc())
            )
            cases_res = await db.execute(cases_stmt)
            cases = cases_res.scalars().all()
            if not cases:
                raise ValueError(f"Dataset '{ds.name}' has 0 test cases. Add test cases before running evaluation.")

            bench_cases = []
            for tc in cases:
                evidence = []
                for ev in tc.ground_truth_evidence or []:
                    try:
                        evidence.append(EvidenceAnchor.model_validate(ev))
                    except Exception:
                        pass
                bench_cases.append(
                    BenchmarkTestCase(
                        id=tc.case_identifier or str(tc.id),
                        query=tc.query,
                        conversation_history=tc.conversation_history or [],
                        query_type=tc.query_type or "single_hop",
                        expected_behavior=tc.expected_behavior or "answer",
                        ground_truth_answer=tc.ground_truth_answer,
                        key_facts=tc.key_facts or [],
                        ground_truth_evidence=evidence,
                        metadata=tc.metadata_json or {},
                    )
                )

            return BenchmarkDataset(
                dataset_name=ds.name,
                description=ds.description,
                version=ds.version,
                test_cases=bench_cases,
            )

        # Fallback to file-based golden dataset
        dataset_path = BENCHMARKS_DIR / f"{dataset_name}.json"
        if not dataset_path.exists():
            dataset_path = BENCHMARKS_DIR / "golden_dataset.json"

        with open(dataset_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return BenchmarkDataset.model_validate(data)

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

        benchmark_input = await EvaluationService.load_benchmark_dataset(
            db=db,
            org_id=org_id,
            dataset_name=payload.dataset_name,
            dataset_id=payload.dataset_id,
        )

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
            dataset_input=benchmark_input,
            run_name=f"api-run-{int(datetime.now().timestamp())}",
            limit=bounded_limit,
        )

        if payload.dataset_id is not None:
            run_model.dataset_id = payload.dataset_id
            await db.commit()
            await db.refresh(run_model)

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

    @staticmethod
    async def create_pending_run(
        db: AsyncSession,
        org_id: uuid.UUID,
        payload: EvaluationRunCreate,
    ) -> EvaluationRunDetail:
        """
        Initializes an evaluation run record in PENDING status for asynchronous execution.
        Enforces hard server-side limit cap of MAX_EVAL_CASES (50).
        """
        MAX_EVAL_CASES = 50
        requested_limit = payload.limit if payload.limit is not None else MAX_EVAL_CASES
        bounded_limit = max(1, min(requested_limit, MAX_EVAL_CASES))

        judge_mode = payload.judge_type.strip().lower()
        judge_name = "LLMJudge" if judge_mode == "llm" else "DeterministicJudge"
        is_offline = payload.offline if judge_mode != "llm" else False

        if payload.dataset_id is not None:
            ds_check = await db.execute(
                select(EvalDataset).where(EvalDataset.id == payload.dataset_id, EvalDataset.org_id == org_id)
            )
            dataset_record = ds_check.scalar_one_or_none()
            if not dataset_record:
                raise ValueError(f"Dataset {payload.dataset_id} was not found for this organization.")

            count_stmt = select(func.count(EvalTestCase.id)).where(
                EvalTestCase.dataset_id == payload.dataset_id, EvalTestCase.org_id == org_id
            )
            tc_count = (await db.execute(count_stmt)).scalar_one()
            if tc_count == 0:
                raise ValueError(f"Cannot run evaluation on empty dataset '{dataset_record.name}'. Add test cases first.")

            effective_total = min(bounded_limit, tc_count)
            eff_dataset_name = dataset_record.name
            eff_dataset_version = dataset_record.version
            eff_dataset_id = payload.dataset_id
        else:
            effective_total = bounded_limit
            eff_dataset_name = payload.dataset_name
            eff_dataset_version = "1.0.0"
            eff_dataset_id = None

        run_id = uuid.uuid4()
        eval_run = EvalRun(
            id=run_id,
            org_id=org_id,
            dataset_id=eff_dataset_id,
            dataset_name=eff_dataset_name,
            dataset_version=eff_dataset_version,
            status="PENDING",
            llm_provider="gemini" if judge_mode == "llm" else "deterministic-offline",
            llm_model="gemini-2.5-flash" if judge_mode == "llm" else "deterministic",
            embedding_model="feature-hashing" if is_offline else "text-embedding-3-small",
            reranker_model="deterministic-cross-scoring",
            total_test_cases=effective_total,
            passed_test_cases=0,
            progress_current=0,
            progress_total=effective_total,
            error_message=None,
            config_snapshot={
                "offline": is_offline,
                "judge": judge_name,
                "limit": bounded_limit,
                "top_k_retrieval": 10,
                "top_k_rerank": 5,
                "dataset_name": eff_dataset_name,
                "dataset_id": str(eff_dataset_id) if eff_dataset_id else None,
                "run_name": f"async-run-{int(datetime.now().timestamp())}",
            },
            summary_metrics={},
            regression_summary={},
            created_at=datetime.now(timezone.utc),
        )
        db.add(eval_run)
        await db.commit()
        await db.refresh(eval_run)

        _active_run_ids.add(run_id)
        return _to_run_detail(eval_run)

    @staticmethod
    async def recover_orphaned_runs(session_factory=None) -> int:
        """
        Recovers evaluation runs left in PENDING or RUNNING status after a server restart.
        Ensures that runs currently actively executing in this process (_active_run_ids)
        are NOT falsely marked as failed.
        """
        from app.core.database import get_session_factory
        session_maker = session_factory or get_session_factory()

        async with session_maker() as db:
            stmt = select(EvalRun).where(EvalRun.status.in_(["PENDING", "RUNNING"]))
            res = await db.execute(stmt)
            candidate_runs = res.scalars().all()

            recovered_count = 0
            for run in candidate_runs:
                # Do not falsely mark an actively running task as failed
                if run.id in _active_run_ids:
                    continue

                run.status = "FAILED"
                run.completed_at = datetime.now(timezone.utc)
                run.error_message = (
                    "Evaluation run was interrupted by a server restart or process termination."
                )
                if not run.summary_metrics:
                    run.summary_metrics = {}
                run.summary_metrics["error"] = "Server restart interrupted evaluation run"
                recovered_count += 1

            if recovered_count > 0:
                await db.commit()
                logger.info(f"Recovered {recovered_count} orphaned evaluation run(s) from previous execution.")

            return recovered_count

    @staticmethod
    async def mark_in_flight_runs_as_interrupted(session_factory=None) -> int:
        """
        Cleanly marks any actively running evaluation runs as FAILED during graceful server shutdown.
        """
        if not _active_run_ids:
            return 0

        from app.core.database import get_session_factory
        session_maker = session_factory or get_session_factory()

        async with session_maker() as db:
            target_ids = list(_active_run_ids)
            stmt = select(EvalRun).where(
                EvalRun.id.in_(target_ids),
                EvalRun.status.in_(["PENDING", "RUNNING"]),
            )
            res = await db.execute(stmt)
            in_flight = res.scalars().all()

            for run in in_flight:
                run.status = "FAILED"
                run.completed_at = datetime.now(timezone.utc)
                run.error_message = "Evaluation run was interrupted by server shutdown."
                if not run.summary_metrics:
                    run.summary_metrics = {}
                run.summary_metrics["error"] = "Server shutdown interrupted evaluation run"

            if in_flight:
                await db.commit()
            _active_run_ids.clear()
            return len(in_flight)


async def process_evaluation_run_background(
    run_id: uuid.UUID,
    org_id: uuid.UUID,
    dataset_name: str,
    judge_type: str,
    limit: Optional[int],
    offline: bool,
    session_factory=None,
    dataset_id: Optional[uuid.UUID] = None,
) -> None:
    """
    Background worker task for asynchronous evaluation runs.
    Uses its own dedicated database session from session_factory.
    Updates EvalRun status from PENDING -> RUNNING -> COMPLETED (or FAILED).
    Tracks incremental progress_current and records error_message on failure.
    """
    from app.core.database import get_session_factory
    from sqlalchemy import update

    _active_run_ids.add(run_id)

    session_maker = session_factory or get_session_factory()

    MAX_EVAL_CASES = 50
    requested_limit = limit if limit is not None else MAX_EVAL_CASES
    bounded_limit = max(1, min(requested_limit, MAX_EVAL_CASES))

    judge_mode = judge_type.strip().lower()
    if judge_mode == "llm":
        judge = LLMJudge()
        is_offline = False
    else:
        judge = DeterministicJudge()
        is_offline = offline

    try:
        async with session_maker() as db:
            try:
                benchmark_input = await EvaluationService.load_benchmark_dataset(
                    db=db,
                    org_id=org_id,
                    dataset_name=dataset_name,
                    dataset_id=dataset_id,
                )
                runner = EvalRunner(
                    db=db,
                    org_id=org_id,
                    judge=judge,
                    offline=is_offline,
                )
                logger.info(
                    f"Starting background evaluation run {run_id} for org {org_id} "
                    f"(dataset: {dataset_name}, judge: {judge_mode}, limit: {bounded_limit})"
                )
                await runner.run_benchmark(
                    dataset_input=benchmark_input,
                    run_name=f"async-run-{int(datetime.now().timestamp())}",
                    limit=bounded_limit,
                    existing_run_id=run_id,
                )
                logger.info(f"Background evaluation run {run_id} completed successfully.")
            except Exception as exc:
                logger.error(
                    f"Background evaluation run {run_id} encountered fatal exception: {exc}",
                    exc_info=True,
                )
                try:
                    update_stmt = (
                        update(EvalRun)
                        .where(EvalRun.id == run_id)
                        .values(
                            status="FAILED",
                            completed_at=datetime.now(timezone.utc),
                            error_message=str(exc),
                            summary_metrics={"error": str(exc)},
                        )
                    )
                    await db.execute(update_stmt)
                    await db.commit()
                except Exception as commit_exc:
                    logger.error(f"Failed to record FAILED status for run {run_id}: {commit_exc}")
    finally:
        _active_run_ids.discard(run_id)


evaluation_service = EvaluationService()
