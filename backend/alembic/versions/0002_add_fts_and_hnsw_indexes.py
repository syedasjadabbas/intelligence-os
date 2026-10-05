"""Add FTS GIN index and HNSW vector index on document_chunks

Revision ID: 0002_fts_hnsw_indexes
Revises: 0001_initial_schema
Create Date: 2026-10-04 16:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002_fts_hnsw_indexes"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. HNSW index for cosine distance vector search (vector_cosine_ops)
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw
        ON document_chunks USING hnsw (embedding vector_cosine_ops);
        """
    )

    # 2. PostgreSQL GIN index for full-text keyword search
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_document_chunks_content_fts
        ON document_chunks USING gin (to_tsvector('english', content));
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_content_fts;")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw;")
