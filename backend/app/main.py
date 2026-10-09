import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.api.v1.endpoints import health
from app.core.config import settings
from app.core.database import engine, init_db

# Configure standard logging format
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("intelligence_os")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle management.
    Performs startup checks (database connection & pgvector extensions),
    recovers any orphaned evaluation runs from prior server process termination,
    and cleanly disposes connection pools on shutdown.
    """
    logger.info(
        f"Starting {settings.PROJECT_NAME} v{settings.VERSION} in {settings.ENVIRONMENT} mode..."
    )
    # Initialize database extensions on startup
    await init_db()

    # Recover any orphaned evaluation runs left over from previous process termination
    try:
        from app.services.evaluation_service import evaluation_service
        orphaned_count = await evaluation_service.recover_orphaned_runs()
        if orphaned_count > 0:
            logger.info(f"Recovered {orphaned_count} orphaned evaluation run(s) from prior server process.")
    except Exception as e:
        logger.warning(f"Could not check for orphaned evaluation runs on startup: {e}")

    yield

    # Cleanup resources on shutdown
    logger.info(f"Shutting down {settings.PROJECT_NAME}...")
    try:
        from app.services.evaluation_service import evaluation_service
        await evaluation_service.mark_in_flight_runs_as_interrupted()
    except Exception as e:
        logger.debug(f"Could not cleanly mark in-flight evaluation runs on shutdown: {e}")

    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Enterprise-grade private RAG platform with multi-tenant isolation and hybrid search capabilities.",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configure CORS Middleware
# Explicitly configured for http://localhost:3000 and configured origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API v1 router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Mount top-level /health endpoint
app.include_router(health.router)


@app.get("/", tags=["System"])
async def root():
    """Root endpoint providing platform metadata and navigation links."""
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "docs": "/docs",
        "health": "/health",
        "api_v1": settings.API_V1_STR,
    }
