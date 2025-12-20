"""Session model for user sessions."""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.user import User


class Session(Base, TimestampMixin):
    """User session.

    Each session belongs to an authenticated user and tracks their
    conversations. The session ID is stored in a JWT token.
    """

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="sessions",
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation",
        back_populates="session",
        cascade="all, delete-orphan",
    )
