"""Pydantic schemas for conversation operations."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.message import MessageResponse
from app.schemas.thinker import ThinkerCreate, ThinkerResponse


class ConversationCreate(BaseModel):
    """Schema for creating a new conversation."""

    topic: str = Field(..., min_length=1)
    thinkers: list[ThinkerCreate] = Field(..., min_length=1, max_length=5)


class ConversationResponse(BaseModel):
    """Schema for conversation response."""

    id: str
    session_id: str
    topic: str
    title: str | None
    is_active: bool
    created_at: datetime
    thinkers: list[ThinkerResponse]

    model_config = {"from_attributes": True}


class ConversationSummary(ConversationResponse):
    """Schema for conversation list with message count and cost."""

    message_count: int = 0
    total_cost: float = 0.0


class ConversationWithMessages(ConversationResponse):
    """Schema for conversation with messages."""

    messages: list[MessageResponse]
    total_cost: float = 0.0
