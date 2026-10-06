import json
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env files."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    PROJECT_NAME: str = "Intelligence OS"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, tuple)):
            return [str(i) for i in v]
        return ["http://localhost:3000"]

    # PostgreSQL Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "intelligence_os"
    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/intelligence_os"
    )
    SYNC_DATABASE_URL: str = (
        "postgresql://postgres:postgres@localhost:5432/intelligence_os"
    )

    # Redis Cache & Message Broker
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security & JWT
    JWT_SECRET_KEY: str = "dev-secret-key-change-this-in-production-min-32-chars-long"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Document Storage & Ingestion Limits
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_BYTES: int = 20 * 1024 * 1024  # 20MB limit
    ALLOWED_EXTENSIONS: List[str] = [".pdf"]

    # AI Vector Embeddings & Hybrid Retrieval
    OPENAI_API_KEY: str = ""
    COHERE_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIM: int = 1536
    RRF_K: int = 60

    # RAG Generation, Reranking & Guardrails
    LLM_PROVIDER: str = "gemini"
    LLM_MODEL: str = "gpt-4o-mini"
    GEMINI_MODEL: str = "gemini-2.5-flash"
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    RERANK_TOP_K: int = 5
    MAX_CONTEXT_TOKENS: int = 2000
    GUARDRAIL_SCORE_THRESHOLD: float = 0.45  # Reduced from 0.75 -> 0.45 to prevent false refusal on moderate relevance chunks
    SIMILARITY_SCORE_THRESHOLD: float = 0.45
    INSUFFICIENT_EVIDENCE_PHRASE: str = (
        "I cannot find sufficient evidence in the organization's documents to answer this question."
    )

    @property
    def upload_path(self):
        from pathlib import Path
        path = Path(self.UPLOAD_DIR)
        if not path.is_absolute():
            backend_dir = Path(__file__).resolve().parent.parent.parent
            path = backend_dir / self.UPLOAD_DIR
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()
# Ensure upload directory is initialized on startup
settings.upload_path
