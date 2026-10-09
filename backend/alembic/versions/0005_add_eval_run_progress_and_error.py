"""Add progress tracking and error message columns to eval_runs

Revision ID: 0005_add_eval_run_progress_and_error
Revises: 0004_add_phase2_eval_metrics
Create Date: 2026-10-09 15:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0005_add_eval_run_progress_and_error"
down_revision: Union[str, None] = "0004_add_phase2_eval_metrics"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "eval_runs",
        sa.Column("progress_current", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "eval_runs",
        sa.Column("progress_total", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "eval_runs",
        sa.Column("error_message", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("eval_runs", "error_message")
    op.drop_column("eval_runs", "progress_total")
    op.drop_column("eval_runs", "progress_current")
