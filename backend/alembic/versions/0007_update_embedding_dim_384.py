"""Update document_chunks embedding dimension from 1536 to 384

Revision ID: 0007_update_embedding_dim_384
Revises: 0006_add_eval_datasets
Create Date: 2026-10-24 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "0007_update_embedding_dim_384"
down_revision: Union[str, None] = "0006_add_eval_datasets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Drop existing HNSW index
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw;")

    # 2. Alter column type to vector(384)
    # Existing 1536-dim vectors are reset to NULL so chunks can be cleanly re-embedded
    op.execute(
        "ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(384) USING NULL;"
    )

    # 3. Recreate HNSW vector index with vector_cosine_ops for 384-dim vectors
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw
        ON document_chunks USING hnsw (embedding vector_cosine_ops);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw;")
    op.execute(
        "ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(1536) USING NULL;"
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw
        ON document_chunks USING hnsw (embedding vector_cosine_ops);
        """
    )
