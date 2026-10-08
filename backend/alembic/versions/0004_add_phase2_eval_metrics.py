"""Add Phase 2 evaluation metrics columns to eval_runs and eval_run_results

Revision ID: 0004_add_phase2_eval_metrics
Revises: 0003_add_eval_tables
Create Date: 2026-10-08 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0004_add_phase2_eval_metrics"
down_revision: Union[str, None] = "0003_add_eval_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add Phase 2 columns to eval_runs
    op.add_column("eval_runs", sa.Column("ndcg_at_5", sa.Float(), nullable=True))
    op.add_column("eval_runs", sa.Column("mean_faithfulness", sa.Float(), nullable=True))
    op.add_column("eval_runs", sa.Column("mean_correctness", sa.Float(), nullable=True))
    op.add_column("eval_runs", sa.Column("mean_completeness", sa.Float(), nullable=True))
    op.add_column("eval_runs", sa.Column("mean_citation_correctness", sa.Float(), nullable=True))
    op.add_column("eval_runs", sa.Column("mean_latency_ms", sa.Float(), nullable=True))

    # 2. Add Phase 2 columns to eval_run_results
    op.add_column("eval_run_results", sa.Column("ndcg_at_5", sa.Float(), nullable=True))
    op.add_column("eval_run_results", sa.Column("faithfulness", sa.Float(), nullable=True))
    op.add_column("eval_run_results", sa.Column("correctness", sa.Float(), nullable=True))
    op.add_column("eval_run_results", sa.Column("completeness", sa.Float(), nullable=True))
    op.add_column("eval_run_results", sa.Column("citation_correctness", sa.Float(), nullable=True))


def downgrade() -> None:
    # 1. Drop columns from eval_run_results
    op.drop_column("eval_run_results", "citation_correctness")
    op.drop_column("eval_run_results", "completeness")
    op.drop_column("eval_run_results", "correctness")
    op.drop_column("eval_run_results", "faithfulness")
    op.drop_column("eval_run_results", "ndcg_at_5")

    # 2. Drop columns from eval_runs
    op.drop_column("eval_runs", "mean_latency_ms")
    op.drop_column("eval_runs", "mean_citation_correctness")
    op.drop_column("eval_runs", "mean_completeness")
    op.drop_column("eval_runs", "mean_correctness")
    op.drop_column("eval_runs", "mean_faithfulness")
    op.drop_column("eval_runs", "ndcg_at_5")
