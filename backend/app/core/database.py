import logging
from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


# Configure initial Asynchronous SQLAlchemy Engine using asyncpg
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

# Setup async_sessionmaker for session injection
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

_session_factory = AsyncSessionLocal


def get_session_factory():
    """Retrieve the active async session factory."""
    return _session_factory


def set_session_factory(factory):
    """Set or override the active async session factory (e.g. for testing)."""
    global _session_factory
    _session_factory = factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency helper to yield an asynchronous database session."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """
    Verify database connectivity and ensure required PostgreSQL extensions exist:
    - uuid-ossp (UUID generation for entities and multi-tenant keys)
    - vector (pgvector extension for high-dimensional vector embeddings)

    If PostgreSQL is unreachable (e.g. Docker container offline in local environment),
    seamlessly falls back to a persistent local SQLite database ('intelligence_os_dev.db')
    and creates all tables so the application remains fully usable.
    """
    global engine, AsyncSessionLocal, _session_factory
    import app.models  # ensure models are registered on Base.metadata

    logger.info("Verifying database connectivity and ensuring PostgreSQL extensions exist...")
    try:
        async with engine.begin() as conn:
            await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
            await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "vector";'))
        logger.info("PostgreSQL extensions ('uuid-ossp', 'vector') verified successfully.")
    except Exception as exc:
        logger.warning(
            f"PostgreSQL connection to {settings.DATABASE_URL} failed ({exc}). "
            "Switching to local persistent SQLite database ('intelligence_os_dev.db') for offline development..."
        )
        sqlite_url = "sqlite+aiosqlite:///intelligence_os_dev.db"
        engine = create_async_engine(
            sqlite_url,
            echo=settings.DEBUG,
            future=True,
            connect_args={"check_same_thread": False},
        )
        AsyncSessionLocal = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        set_session_factory(AsyncSessionLocal)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Local SQLite database initialized with full schema.")
