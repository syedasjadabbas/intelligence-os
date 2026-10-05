"""FastAPI dependencies re-exported for convenience."""
from app.api.deps import (
    get_db,
    get_redis,
    get_current_user,
    get_current_active_admin,
    get_current_tenant,
    oauth2_scheme,
)

__all__ = [
    "get_db",
    "get_redis",
    "get_current_user",
    "get_current_active_admin",
    "get_current_tenant",
    "oauth2_scheme",
]
