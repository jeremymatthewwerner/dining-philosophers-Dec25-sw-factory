"""Pydantic schemas for message operations."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.message import SenderType


class MessageCreate(BaseModel):
    """Schema for creating a message."""

    content: str = Field(..., min_length=1)


class MessageResponse(BaseModel):
    """Schema for message response."""

    id: str
    conversation_id: str
    sender_type: SenderType
    sender_name: str | None
    content: str
    cost: float | None
    created_at: datetime

    model_config = {"from_attributes": True}
