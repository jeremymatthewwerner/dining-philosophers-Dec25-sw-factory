"""User model for authentication."""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.models.session import Session


class User(Base, TimestampMixin):
    """Authenticated user account.

    Users can register with username/password. Each user has their own
    sessions and conversations. Admin users can view all users.
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    is_admin: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    total_spend: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    spend_limit: Mapped[float] = mapped_column(
        Float,
        default=10.0,  # Default $10 limit per user
        nullable=False,
    )
    display_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Relationships
    sessions: Mapped[list["Session"]] = relationship(
        "Session",
        back_populates="user",
        cascade="all, delete-orphan",
    )
