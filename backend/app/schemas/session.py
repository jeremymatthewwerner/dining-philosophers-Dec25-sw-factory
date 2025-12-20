"""Pydantic schemas for session operations."""

from datetime import datetime

from pydantic import BaseModel


class SessionCreate(BaseModel):
    """Schema for creating a new session."""

    pass


class SessionResponse(BaseModel):
    """Schema for session response."""

    id: str
    created_at: datetime

    model_config = {"from_attributes": True}
