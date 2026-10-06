import re
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.schemas.auth import AuthResponse, LoginRequest, OrgRegisterRequest, Token
from app.schemas.org import OrgResponse
from app.schemas.user import UserProfileResponse, UserResponse

router = APIRouter()


def slugify(text: str) -> str:
    """Generate a clean URL-friendly slug from an organization name."""
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-") or "org"


@router.post(
    "/register-org",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new organization & initial Admin user",
)
async def register_organization(
    data: OrgRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """
    Creates a new multi-tenant Organization, assigns the initial Admin user,
    and returns a signed JWT access token with the user profile.
    """
    slug = (data.org_slug.strip().lower() if data.org_slug else slugify(data.org_name))

    # Check if slug is already taken
    existing_org = await db.execute(
        select(Organization).where(Organization.slug == slug)
    )
    if existing_org.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Organization with slug '{slug}' already exists. Please choose a different name or slug.",
        )

    # Check if email is already in use
    existing_user = await db.execute(
        select(User).where(User.email == data.admin_email.lower())
    )
    if existing_user.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email '{data.admin_email}' is already registered.",
        )

    # 1. Create Organization
    org = Organization(
        id=uuid.uuid4(),
        name=data.org_name.strip(),
        slug=slug,
    )
    db.add(org)
    await db.flush()

    # 2. Create Initial Admin User
    admin_user = User(
        id=uuid.uuid4(),
        org_id=org.id,
        email=data.admin_email.lower(),
        hashed_password=get_password_hash(data.admin_password),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(admin_user)
    await db.commit()
    await db.refresh(org)
    await db.refresh(admin_user)

    # 3. Issue JWT Access Token
    role_str = admin_user.role.value if hasattr(admin_user.role, "value") else str(admin_user.role)
    access_token = create_access_token(
        subject=admin_user.id,
        org_id=org.id,
        role=role_str,
    )

    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(admin_user),
        organization=OrgResponse.model_validate(org),
    )


@router.post(
    "/token",
    response_model=Token,
    summary="Login / Token exchange via JSON or OAuth2 Form Data",
)
@router.post(
    "/login",
    response_model=Token,
    summary="Login via JSON or OAuth2 Form Data",
)
async def login(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Token:
    """
    Authenticates a user using email and password.
    Supports both JSON body and standard OAuth2 application/x-www-form-urlencoded format.
    """
    content_type = request.headers.get("content-type", "")
    email: Optional[str] = None
    password: Optional[str] = None

    if "application/json" in content_type:
        try:
            body = await request.json()
            email = body.get("email") or body.get("username")
            password = body.get("password")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON payload",
            )
    else:
        try:
            form = await request.form()
            email = form.get("username") or form.get("email")
            password = form.get("password")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid form data",
            )

    if not email or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both email/username and password are required",
        )

    # Lookup user
    stmt = select(User).where(User.email == email.strip().lower())
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
    access_token = create_access_token(
        subject=user.id,
        org_id=user.org_id,
        role=role_str,
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
    )


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get current authenticated user profile & organization",
)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    """Returns profile information for the authenticated user and their tenant organization."""
    org_stmt = select(Organization).where(Organization.id == current_user.org_id)
    org_res = await db.execute(org_stmt)
    org = org_res.scalar_one_or_none()

    return UserProfileResponse(
        id=current_user.id,
        org_id=current_user.org_id,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        organization=OrgResponse.model_validate(org) if org else None,
    )
