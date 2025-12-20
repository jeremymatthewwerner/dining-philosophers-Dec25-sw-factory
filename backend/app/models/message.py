"""Message model for chat messages."""

from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.models.conversation import Conversation


class SenderType(str, Enum):
    """Type of message sender."""

    USER = "user"
    THINKER = "thinker"
    SYSTEM = "system"


class Message(Base, TimestampMixin):
    """A message in a conversation.

    Messages can be from the user, a thinker, or the system.
    Thinker messages include the thinker's name for display.
    """

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_type: Mapped[SenderType] = mapped_column(
        String(20),
        nullable=False,
    )
    sender_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    cost: Mapped[float | None] = mapped_column(
        nullable=True,
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages",
    )
