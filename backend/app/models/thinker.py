"""ConversationThinker model for thinkers participating in conversations."""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.models.conversation import Conversation


class ConversationThinker(Base, TimestampMixin):
    """A thinker participating in a specific conversation.

    Each thinker has a profile with biographical info, known positions,
    and communication style. This information is used to prompt the LLM
    to simulate the thinker's responses.
    """

    __tablename__ = "conversation_thinkers"

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
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    bio: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    positions: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    style: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    color: Mapped[str] = mapped_column(
        String(7),
        nullable=False,
        default="#6366f1",
    )
    image_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="thinkers",
    )
