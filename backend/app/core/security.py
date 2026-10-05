from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union
import uuid
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# CryptContext configured with bcrypt algorithm
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate a bcrypt hash of a plain-text password."""
    return pwd_context.hash(password)


def create_access_token(
    subject: Union[str, uuid.UUID],
    org_id: Union[str, uuid.UUID],
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Generate a signed JWT access token containing subject (user_id),
    organization ID (org_id), user role, and expiration timestamp.
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode: Dict[str, Any] = {
        "sub": str(subject),
        "org_id": str(org_id),
        "role": str(role),
        "exp": expire,
        "iat": now,
    }
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and validate a JWT access token.
    Returns the claims dictionary if valid, or None if expired/invalid.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError:
        return None
