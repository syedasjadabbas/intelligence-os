from typing import Optional
from pydantic import BaseModel, EmailStr
from app.schemas.org import OrgResponse
from app.schemas.user import UserResponse


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: Optional[str] = None
    org_id: Optional[str] = None
    role: Optional[str] = None


class OrgRegisterRequest(BaseModel):
    org_name: str
    org_slug: Optional[str] = None
    admin_email: EmailStr
    admin_password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    organization: OrgResponse
