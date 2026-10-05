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
    Performs startup checks (database connection & pgvector extensions)
    and clean shutdown (disposes connection pools).
    """
    logger.info(
        f"Starting {settings.PROJECT_NAME} v{settings.VERSION} in {settings.ENVIRONMENT} mode..."
    )
    # Initialize database extensions on startup
    await init_db()
    yield
    # Cleanup resources on shutdown
    logger.info(f"Shutting down {settings.PROJECT_NAME}...")
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
