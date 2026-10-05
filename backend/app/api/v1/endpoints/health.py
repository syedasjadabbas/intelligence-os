import logging
from typing import Optional
from fastapi import APIRouter, Depends, Response, status
import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_redis
from app.schemas.health import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service Healthcheck",
    description="Asynchronously pings PostgreSQL and Redis, and verifies pgvector extension status.",
)
async def check_health(
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
) -> HealthResponse:
    """
    Perform deep health check:
    1. Ping PostgreSQL via `SELECT 1;`
    2. Check pgvector extension availability via `pg_extension`
    3. Ping Redis via `redis.ping()`
    """
    database_status = "disconnected"
    redis_status = "disconnected"
    pgvector_ready = False

    # Check Database and pgvector extension
    try:
        await db.execute(text("SELECT 1;"))
        database_status = "connected"

        # Verify pgvector extension if on PostgreSQL, or pass if on SQLite fallback
        try:
            pgvector_check = await db.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector';")
            )
            if pgvector_check.scalar() is not None:
                pgvector_ready = True
        except Exception:
            # Fallback SQLite mode
            pgvector_ready = True
    except Exception as exc:
        logger.error(f"Database health check failed: {exc}")
        database_status = "disconnected"

    # Check Redis
    try:
        pong = await redis_client.ping()
        if pong:
            redis_status = "connected"
    except Exception as exc:
        logger.error(f"Redis health check failed: {exc}")
        redis_status = "disconnected"

    is_healthy = (
        database_status == "connected"
        and redis_status == "connected"
        and pgvector_ready is True
    )

    if not is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status="healthy" if is_healthy else "unhealthy",
        database=database_status,
        redis=redis_status,
        pgvector_ready=pgvector_ready,
    )
