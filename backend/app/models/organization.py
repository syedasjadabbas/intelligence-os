import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List
from sqlalchemy import DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.document import Document
    from app.models.conversation import Conversation


class Organization(Base):
    """
    Tenant organization model for strict multi-tenant data isolation.
    All enterprise resources (users, documents, conversations) are scoped to an organization.
    """

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    users: Mapped[List["User"]] = relationship(
        "User",
        back_populates="organization",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    documents: Mapped[List["Document"]] = relationship(
        "Document",
        back_populates="organization",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    conversations: Mapped[List["Conversation"]] = relationship(
        "Conversation",
        back_populates="organization",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
