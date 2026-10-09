import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.organization import Organization


class EvalRun(Base):
    """
    Evaluation execution run scoped to an enterprise tenant organization.
    Stores benchmark configuration, execution metadata, and aggregate metrics.
    """

    __tablename__ = "eval_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    dataset_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    dataset_version: Mapped[str] = mapped_column(
        String(50),
        default="1.0.0",
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="PENDING",
        nullable=False,
        index=True,
    )  # PENDING, RUNNING, COMPLETED, FAILED

    # Provider & model metadata
    llm_provider: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    llm_model: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    embedding_model: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    reranker_model: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Test case counts & progress tracking
    total_test_cases: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    passed_test_cases: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    progress_current: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    progress_total: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Strongly typed aggregate metrics
    recall_at_3: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    recall_at_5: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    mrr: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    ndcg_at_5: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    citation_precision: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    citation_coverage: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    correct_refusal_rate: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    false_refusal_rate: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    mean_faithfulness: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    mean_correctness: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    mean_completeness: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    mean_citation_correctness: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    mean_latency_ms: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    latency_p95_ms: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )

    # JSON configuration snapshot & detailed metrics
    config_snapshot: Mapped[Dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        default=dict,
        nullable=False,
    )
    summary_metrics: Mapped[Dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        default=dict,
        nullable=False,
    )
    regression_summary: Mapped[Dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        default=dict,
        nullable=False,
    )

    # Timestamps
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
    )
    results: Mapped[List["EvalRunResult"]] = relationship(
        "EvalRunResult",
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class EvalRunResult(Base):
    """
    Per-test-case result within an evaluation run.
    Stores query inputs, retrieved chunks, generated response, citations, trace, and metric scores.
    """

    __tablename__ = "eval_run_results"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("eval_runs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    test_case_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    query: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    query_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    expected_behavior: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )  # answer, refuse
    generated_answer: Mapped[str] = mapped_column(
        Text,
        default="",
        nullable=False,
    )
    passed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    is_refusal: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Strongly typed per-case metrics
    recall_at_3: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    recall_at_5: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    mrr: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    ndcg_at_5: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    citation_precision: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    citation_coverage: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    faithfulness: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    correctness: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    completeness: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    citation_correctness: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    total_latency_ms: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )

    # JSON structures for inspection
    retrieved_candidates: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        default=list,
        nullable=False,
    )
    reranked_candidates: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        default=list,
        nullable=False,
    )
    citations: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        default=list,
        nullable=False,
    )
    trace_data: Mapped[Dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        default=dict,
        nullable=False,
    )
    judge_output: Mapped[Dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        default=dict,
        nullable=False,
    )

    failure_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    # Table arguments & indexes
    __table_args__ = (
        Index("ix_eval_run_results_run_id_test_case_id", "run_id", "test_case_id"),
    )

    # Relationships
    run: Mapped["EvalRun"] = relationship(
        "EvalRun",
        back_populates="results",
    )
