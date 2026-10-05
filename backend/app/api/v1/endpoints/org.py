from typing import List
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_active_admin,
    get_current_tenant,
    get_current_user,
    get_db,
)
from app.core.security import get_password_hash
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.schemas.org import OrgResponse
from app.schemas.user import UserCreate, UserResponse

router = APIRouter()


@router.get(
    "",
    response_model=OrgResponse,
    summary="Get current tenant organization details",
)
async def get_current_organization(
    org_id: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> OrgResponse:
    """Returns organization metadata for the authenticated tenant."""
    stmt = select(Organization).where(Organization.id == org_id)
    result = await db.execute(stmt)
    org = result.scalar_one_or_none()

    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    return OrgResponse.model_validate(org)


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create/invite user to organization (Admin only)",
)
async def create_org_user(
    data: UserCreate,
    admin_user: User = Depends(get_current_active_admin),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Creates a new user strictly scoped to the admin's organization.
    Only users with the ADMIN role can execute this endpoint.
    """
    # Check if email is already taken
    existing = await db.execute(
        select(User).where(User.email == data.email.strip().lower())
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with email '{data.email}' already exists.",
        )

    new_user = User(
        id=uuid.uuid4(),
        org_id=admin_user.org_id,
        email=data.email.strip().lower(),
        hashed_password=get_password_hash(data.password),
        role=data.role or UserRole.MEMBER,
        is_active=True,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return UserResponse.model_validate(new_user)


@router.get(
    "/users",
    response_model=List[UserResponse],
    summary="List all users in the authenticated organization",
)
async def list_org_users(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[UserResponse]:
    """
    Lists all users belonging to the caller's organization.
    Multi-tenant isolation is strictly enforced via org_id filter.
    """
    stmt = (
        select(User)
        .where(User.org_id == current_user.org_id)
        .order_by(User.created_at.asc())
    )
    result = await db.execute(stmt)
    users = result.scalars().all()

    return [UserResponse.model_validate(u) for u in users]
