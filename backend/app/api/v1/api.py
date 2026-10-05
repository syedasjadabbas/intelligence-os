from fastapi import APIRouter
from app.api.v1.endpoints import auth, chat, documents, health, org, search

api_router = APIRouter()

# System Healthcheck
api_router.include_router(health.router, tags=["Health"])

# Authentication & Registration
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])

# Organization & User Management (Multi-tenant)
api_router.include_router(org.router, prefix="/org", tags=["Organizations & Users"])

# Document Ingestion & Chunk Management
api_router.include_router(
    documents.router, prefix="/documents", tags=["Documents & Ingestion"]
)

# Hybrid Search & RRF Retrieval
api_router.include_router(
    search.router, prefix="/search", tags=["Search & Retrieval"]
)

# Conversations & Grounded Chat (RAG)
api_router.include_router(
    chat.router, prefix="/chat", tags=["Conversations & Chat"]
)
