"""Add eval_datasets and eval_test_cases tables, add dataset_id to eval_runs

Revision ID: 0006_add_eval_datasets
Revises: 0005_add_eval_run_progress_and_error
Create Date: 2026-10-09 16:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0006_add_eval_datasets"
down_revision: Union[str, None] = "0005_add_eval_run_progress_and_error"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create eval_datasets table
    op.create_table(
        "eval_datasets",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("org_id", sa.Uuid(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.String(length=50), server_default="1.0.0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("org_id", "name", name="uq_eval_datasets_org_name"),
    )
    op.create_index("ix_eval_datasets_id", "eval_datasets", ["id"])
    op.create_index("ix_eval_datasets_org_id", "eval_datasets", ["org_id"])
    op.create_index("ix_eval_datasets_name", "eval_datasets", ["name"])

    # 2. Create eval_test_cases table
    op.create_table(
        "eval_test_cases",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("dataset_id", sa.Uuid(as_uuid=True), sa.ForeignKey("eval_datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", sa.Uuid(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("case_identifier", sa.String(length=100), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("query_type", sa.String(length=50), server_default="single_hop", nullable=False),
        sa.Column("expected_behavior", sa.String(length=20), server_default="answer", nullable=False),
        sa.Column("ground_truth_answer", sa.Text(), nullable=True),
        sa.Column(
            "key_facts",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "ground_truth_evidence",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "conversation_history",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "metadata_json",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_eval_test_cases_id", "eval_test_cases", ["id"])
    op.create_index("ix_eval_test_cases_dataset_id", "eval_test_cases", ["dataset_id"])
    op.create_index("ix_eval_test_cases_org_id", "eval_test_cases", ["org_id"])
    op.create_index("ix_eval_test_cases_dataset_case", "eval_test_cases", ["dataset_id", "case_identifier"])

    # 3. Add dataset_id to eval_runs
    op.add_column(
        "eval_runs",
        sa.Column(
            "dataset_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("eval_datasets.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_eval_runs_dataset_id", "eval_runs", ["dataset_id"])


def downgrade() -> None:
    op.drop_index("ix_eval_runs_dataset_id", table_name="eval_runs")
    op.drop_column("eval_runs", "dataset_id")
    op.drop_table("eval_test_cases")
    op.drop_table("eval_datasets")
