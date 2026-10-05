from datetime import datetime
from typing import Optional
import uuid
from pydantic import BaseModel, ConfigDict, EmailStr
from app.models.user import UserRole
from app.schemas.org import OrgResponse


class UserBase(BaseModel):
    email: EmailStr
    role: UserRole = UserRole.MEMBER


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: uuid.UUID
    org_id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserProfileResponse(UserResponse):
    organization: Optional[OrgResponse] = None

    model_config = ConfigDict(from_attributes=True)
