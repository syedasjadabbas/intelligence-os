from typing import AsyncGenerator
import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session_factory
from app.core.security import decode_access_token
from app.models.user import User, UserRole

# OAuth2 password bearer scheme pointing to the login endpoint
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login"
)


class MockRedis:
    """In-memory async Redis mock for local development when Redis container is offline."""
    def __init__(self):
        self._store = {}

    async def ping(self):
        return True

    async def get(self, key):
        return self._store.get(str(key))

    async def set(self, key, value, ex=None):
        self._store[str(key)] = str(value)
        return True

    async def delete(self, *keys):
        count = 0
        for k in keys:
            if str(k) in self._store:
                del self._store[str(k)]
                count += 1
        return count

    async def exists(self, key):
        return 1 if str(key) in self._store else 0

    async def close(self):
        pass


_mock_redis = MockRedis()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an asynchronous SQLAlchemy database session."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """FastAPI dependency yielding an asynchronous Redis client with local fallback."""
    try:
        client: aioredis.Redis = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=1.0,
        )
        await client.ping()
        try:
            yield client
        finally:
            await client.close()
    except Exception:
        yield _mock_redis


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> User:
    """
    Extracts bearer token from authorization header, decodes and verifies JWT signature,
    and fetches the active user from the database.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id_str: str = payload.get("sub")
    if not user_id_str:
        raise credentials_exception

    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        raise credentials_exception

    stmt = select(User).where(User.id == user_uuid)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )
    return user


async def get_current_active_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Ensures the authenticated user has ADMIN role.
    Raises 403 Forbidden if the user is a standard MEMBER.
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Administrative privileges required",
        )
    return current_user


async def get_current_tenant(
    current_user: User = Depends(get_current_user),
) -> uuid.UUID:
    """
    Extracts and returns the organization ID (org_id) strictly from the authenticated
    user context. Guarantees multi-tenant isolation across all data access operations.
    """
    return current_user.org_id
