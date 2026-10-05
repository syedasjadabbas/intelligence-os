from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Schema representing system health status across core services."""

    status: str = Field(
        ...,
        description="Overall health status ('healthy', 'degraded', or 'unhealthy')",
        examples=["healthy"],
    )
    database: str = Field(
        ...,
        description="PostgreSQL connection status ('connected' or error message)",
        examples=["connected"],
    )
    redis: str = Field(
        ...,
        description="Redis connection status ('connected' or error message)",
        examples=["connected"],
    )
    pgvector_ready: bool = Field(
        ...,
        description="Indicates if the PostgreSQL vector extension is active",
        examples=[True],
    )
