"""Conversation model for chat conversations."""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.models.message import Message
    from app.models.session import Session
    from app.models.thinker import ConversationThinker


class Conversation(Base, TimestampMixin):
    """A chat conversation with multiple thinkers.

    Each conversation has a topic and a set of thinkers who participate.
    Messages are stored separately and linked to this conversation.
    """

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
    )

    # Relationships
    session: Mapped["Session"] = relationship(
        "Session",
        back_populates="conversations",
    )
    thinkers: Mapped[list["ConversationThinker"]] = relationship(
        "ConversationThinker",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
