"""Add eval_runs and eval_run_results tables for RAG evaluation

Revision ID: 0003_add_eval_tables
Revises: 0002_fts_hnsw_indexes
Create Date: 2026-10-08 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003_add_eval_tables"
down_revision: Union[str, None] = "0002_fts_hnsw_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create eval_runs table
    op.create_table(
        "eval_runs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("org_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("dataset_name", sa.String(length=255), nullable=False),
        sa.Column("dataset_version", sa.String(length=50), server_default="1.0.0", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="PENDING", nullable=False),
        sa.Column("llm_provider", sa.String(length=50), nullable=True),
        sa.Column("llm_model", sa.String(length=100), nullable=True),
        sa.Column("embedding_model", sa.String(length=100), nullable=True),
        sa.Column("reranker_model", sa.String(length=100), nullable=True),
        sa.Column("total_test_cases", sa.Integer(), server_default="0", nullable=False),
        sa.Column("passed_test_cases", sa.Integer(), server_default="0", nullable=False),
        sa.Column("recall_at_3", sa.Float(), nullable=True),
        sa.Column("recall_at_5", sa.Float(), nullable=True),
        sa.Column("mrr", sa.Float(), nullable=True),
        sa.Column("citation_precision", sa.Float(), nullable=True),
        sa.Column("citation_coverage", sa.Float(), nullable=True),
        sa.Column("correct_refusal_rate", sa.Float(), nullable=True),
        sa.Column("false_refusal_rate", sa.Float(), nullable=True),
        sa.Column("latency_p95_ms", sa.Float(), nullable=True),
        sa.Column(
            "config_snapshot",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "summary_metrics",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "regression_summary",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name="fk_eval_runs_org_id_organizations",
            ondelete="CASCADE",
        ),
    )
    op.create_index(op.f("ix_eval_runs_id"), "eval_runs", ["id"], unique=False)
    op.create_index(op.f("ix_eval_runs_org_id"), "eval_runs", ["org_id"], unique=False)
    op.create_index(op.f("ix_eval_runs_status"), "eval_runs", ["status"], unique=False)

    # 2. Create eval_run_results table
    op.create_table(
        "eval_run_results",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("run_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("org_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("test_case_id", sa.String(length=100), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("query_type", sa.String(length=50), nullable=False),
        sa.Column("expected_behavior", sa.String(length=20), nullable=False),
        sa.Column("generated_answer", sa.Text(), server_default="", nullable=False),
        sa.Column("passed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("is_refusal", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("recall_at_3", sa.Float(), nullable=True),
        sa.Column("recall_at_5", sa.Float(), nullable=True),
        sa.Column("mrr", sa.Float(), nullable=True),
        sa.Column("citation_precision", sa.Float(), nullable=True),
        sa.Column("citation_coverage", sa.Float(), nullable=True),
        sa.Column("total_latency_ms", sa.Float(), nullable=True),
        sa.Column(
            "retrieved_candidates",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "reranked_candidates",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "citations",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "trace_data",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "judge_output",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["eval_runs.id"],
            name="fk_eval_run_results_run_id_eval_runs",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name="fk_eval_run_results_org_id_organizations",
            ondelete="CASCADE",
        ),
    )
    op.create_index(op.f("ix_eval_run_results_id"), "eval_run_results", ["id"], unique=False)
    op.create_index(op.f("ix_eval_run_results_run_id"), "eval_run_results", ["run_id"], unique=False)
    op.create_index(op.f("ix_eval_run_results_org_id"), "eval_run_results", ["org_id"], unique=False)
    op.create_index(op.f("ix_eval_run_results_test_case_id"), "eval_run_results", ["test_case_id"], unique=False)
    op.create_index(op.f("ix_eval_run_results_passed"), "eval_run_results", ["passed"], unique=False)
    op.create_index(
        "ix_eval_run_results_run_id_test_case_id",
        "eval_run_results",
        ["run_id", "test_case_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_eval_run_results_run_id_test_case_id", table_name="eval_run_results")
    op.drop_index(op.f("ix_eval_run_results_passed"), table_name="eval_run_results")
    op.drop_index(op.f("ix_eval_run_results_test_case_id"), table_name="eval_run_results")
    op.drop_index(op.f("ix_eval_run_results_org_id"), table_name="eval_run_results")
    op.drop_index(op.f("ix_eval_run_results_run_id"), table_name="eval_run_results")
    op.drop_index(op.f("ix_eval_run_results_id"), table_name="eval_run_results")
    op.drop_table("eval_run_results")

    op.drop_index(op.f("ix_eval_runs_status"), table_name="eval_runs")
    op.drop_index(op.f("ix_eval_runs_org_id"), table_name="eval_runs")
    op.drop_index(op.f("ix_eval_runs_id"), table_name="eval_runs")
    op.drop_table("eval_runs")
