"""
Evaluation REST API Endpoints for Intelligence OS.
Provides authenticated, multi-tenant evaluation management, run creation,
result inspection, and side-by-side run comparisons.
"""

import logging
from typing import Optional
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_active_admin,
    get_current_tenant,
    get_current_user,
    get_db,
)
from app.models.user import User
from app.schemas.evaluation import (
    DatasetCreate,
    DatasetDetail,
    DatasetListItem,
    DatasetUpdate,
    DatasetsPage,
    EvaluationComparisonResponse,
    EvaluationResultDetail,
    EvaluationResultsPage,
    EvaluationRunCreate,
    EvaluationRunDetail,
    EvaluationRunsPage,
    TestCaseCreate,
    TestCaseDetail,
    TestCaseUpdate,
)
from app.services.evaluation_service import (
    evaluation_service,
    process_evaluation_run_background,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "",
    response_model=EvaluationRunsPage,
    summary="List evaluation runs",
    description="Lists all benchmark evaluation runs for the authenticated user's organization.",
)
async def list_evaluation_runs(
    skip: int = Query(0, ge=0, description="Number of runs to skip"),
    limit: int = Query(20, ge=1, le=100, description="Max number of runs to return"),
    judge_type: Optional[str] = Query(None, description="Filter by judge type ('deterministic' or 'llm')"),
    status: Optional[str] = Query(None, description="Filter by status ('COMPLETED', 'RUNNING', 'FAILED')"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, total = await evaluation_service.list_runs(
        db=db,
        org_id=current_user.org_id,
        skip=skip,
        limit=limit,
        judge_type=judge_type,
        status=status,
    )
    return EvaluationRunsPage(items=items, total=total, skip=skip, limit=limit)


@router.post(
    "",
    response_model=EvaluationRunDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Start an evaluation run",
    description="Initializes an asynchronous evaluation benchmark run with progress tracking. Requires organization ADMIN role.",
)
async def create_evaluation_run(
    payload: EvaluationRunCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin),
):
    try:
        pending_run = await evaluation_service.create_pending_run(
            db=db,
            org_id=current_admin.org_id,
            payload=payload,
        )

        background_tasks.add_task(
            process_evaluation_run_background,
            run_id=pending_run.id,
            org_id=current_admin.org_id,
            dataset_name=pending_run.dataset_name,
            judge_type=payload.judge_type,
            limit=payload.limit,
            offline=payload.offline,
            dataset_id=payload.dataset_id,
        )

        return pending_run
    except ValueError as ve:
        err_msg = str(ve)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in err_msg.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(
            status_code=status_code,
            detail=err_msg,
        )
    except Exception as e:
        logger.error(f"Failed to initiate evaluation run: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evaluation initiation failed: {str(e)}",
        )


@router.get(
    "/compare",
    response_model=EvaluationComparisonResponse,
    summary="Compare two evaluation runs",
    description="Computes metric deltas and case-level regressions between two evaluation runs belonging to the tenant.",
)
async def compare_evaluation_runs(
    base_run_id: uuid.UUID = Query(..., description="ID of baseline evaluation run"),
    target_run_id: uuid.UUID = Query(..., description="ID of target evaluation run to compare against baseline"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    comparison = await evaluation_service.compare_runs(
        db=db,
        org_id=current_user.org_id,
        base_run_id=base_run_id,
        target_run_id=target_run_id,
    )
    if not comparison:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both evaluation runs not found",
        )
    return comparison


# =========================================================================
# Phase 5B: Evaluation Dataset & Test Case Management Endpoints
# =========================================================================

@router.get(
    "/datasets",
    response_model=DatasetsPage,
    summary="List evaluation datasets",
    description="Lists custom evaluation datasets for the authenticated organization.",
)
async def list_datasets(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, total = await evaluation_service.list_datasets(
        db=db,
        org_id=current_user.org_id,
        skip=skip,
        limit=limit,
    )
    return DatasetsPage(items=items, total=total)


@router.post(
    "/datasets",
    response_model=DatasetDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create evaluation dataset",
    description="Creates a new custom benchmark dataset. Requires ADMIN role.",
)
async def create_dataset(
    payload: DatasetCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin),
):
    try:
        return await evaluation_service.create_dataset(
            db=db,
            org_id=current_admin.org_id,
            payload=payload,
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )


@router.get(
    "/datasets/{dataset_id}",
    response_model=DatasetDetail,
    summary="Get evaluation dataset details",
    description="Retrieves a dataset with all its benchmark test cases.",
)
async def get_dataset(
    dataset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = await evaluation_service.get_dataset(
        db=db,
        org_id=current_user.org_id,
        dataset_id=dataset_id,
    )
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found",
        )
    return dataset


@router.put(
    "/datasets/{dataset_id}",
    response_model=DatasetDetail,
    summary="Update evaluation dataset",
    description="Updates dataset metadata. Requires ADMIN role.",
)
async def update_dataset(
    dataset_id: uuid.UUID,
    payload: DatasetUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin),
):
    try:
        dataset = await evaluation_service.update_dataset(
            db=db,
            org_id=current_admin.org_id,
            dataset_id=dataset_id,
            payload=payload,
        )
        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found",
            )
        return dataset
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )


@router.delete(
    "/datasets/{dataset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete evaluation dataset",
    description="Deletes a dataset and all associated test cases. Requires ADMIN role.",
)
async def delete_dataset(
    dataset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin),
):
    deleted = await evaluation_service.delete_dataset(
        db=db,
        org_id=current_admin.org_id,
        dataset_id=dataset_id,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found",
        )
    return None


@router.post(
    "/datasets/{dataset_id}/cases",
    response_model=TestCaseDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Add test case to dataset",
    description="Adds a benchmark test case to a dataset. Requires ADMIN role.",
)
async def add_test_case(
    dataset_id: uuid.UUID,
    payload: TestCaseCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin),
):
    tc = await evaluation_service.add_test_case(
        db=db,
        org_id=current_admin.org_id,
        dataset_id=dataset_id,
        payload=payload,
    )
    if not tc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found",
        )
    return tc


@router.put(
    "/datasets/{dataset_id}/cases/{case_id}",
    response_model=TestCaseDetail,
    summary="Update test case",
    description="Updates a benchmark test case in a dataset. Requires ADMIN role.",
)
async def update_test_case(
    dataset_id: uuid.UUID,
    case_id: uuid.UUID,
    payload: TestCaseUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin),
):
    tc = await evaluation_service.update_test_case(
        db=db,
        org_id=current_admin.org_id,
        dataset_id=dataset_id,
        case_id=case_id,
        payload=payload,
    )
    if not tc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test case or dataset not found",
        )
    return tc


@router.delete(
    "/datasets/{dataset_id}/cases/{case_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete test case",
    description="Deletes a benchmark test case from a dataset. Requires ADMIN role.",
)
async def delete_test_case(
    dataset_id: uuid.UUID,
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin),
):
    deleted = await evaluation_service.delete_test_case(
        db=db,
        org_id=current_admin.org_id,
        dataset_id=dataset_id,
        case_id=case_id,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test case or dataset not found",
        )
    return None


@router.get(
    "/{run_id}",
    response_model=EvaluationRunDetail,
    summary="Get evaluation run detail",
    description="Retrieves aggregate metrics, configuration snapshot, and metadata for a specific run.",
)
async def get_evaluation_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run = await evaluation_service.get_run(
        db=db,
        org_id=current_user.org_id,
        run_id=run_id,
    )
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation run not found",
        )
    return run


@router.get(
    "/{run_id}/results",
    response_model=EvaluationResultsPage,
    summary="List evaluation case results",
    description="Retrieves paginated test case results with optional filters (passed, query_type, is_refusal).",
)
async def list_evaluation_results(
    run_id: uuid.UUID,
    skip: int = Query(0, ge=0, description="Number of results to skip"),
    limit: int = Query(20, ge=1, le=100, description="Max number of results to return"),
    passed: Optional[bool] = Query(None, description="Filter by pass status"),
    query_type: Optional[str] = Query(None, description="Filter by query category"),
    is_refusal: Optional[bool] = Query(None, description="Filter by refusal flag"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await evaluation_service.list_results(
        db=db,
        org_id=current_user.org_id,
        run_id=run_id,
        skip=skip,
        limit=limit,
        passed=passed,
        query_type=query_type,
        is_refusal=is_refusal,
    )
    if res is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation run not found",
        )

    items, total = res
    return EvaluationResultsPage(items=items, total=total, skip=skip, limit=limit)


@router.get(
    "/{run_id}/results/{result_id}",
    response_model=EvaluationResultDetail,
    summary="Get evaluation case result detail",
    description="Retrieves full test case inspection payload: query, candidates, citations, trace, and judge scoring.",
)
async def get_evaluation_result(
    run_id: uuid.UUID,
    result_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await evaluation_service.get_result(
        db=db,
        org_id=current_user.org_id,
        run_id=run_id,
        result_id=result_id,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation result not found",
        )
    return result
