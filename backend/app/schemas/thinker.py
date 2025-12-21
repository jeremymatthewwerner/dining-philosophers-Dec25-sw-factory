"""Pydantic schemas for thinker operations."""

from datetime import datetime

from pydantic import BaseModel, Field


class ThinkerCreate(BaseModel):
    """Schema for creating a thinker in a conversation."""

    name: str = Field(..., min_length=1, max_length=255)
    bio: str
    positions: str
    style: str
    color: str = Field(default="#6366f1", pattern=r"^#[0-9a-fA-F]{6}$")
    image_url: str | None = None


class ThinkerResponse(BaseModel):
    """Schema for thinker response."""

    id: str
    conversation_id: str
    name: str
    bio: str
    positions: str
    style: str
    color: str
    image_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ThinkerProfile(BaseModel):
    """Profile information for a thinker."""

    name: str
    bio: str
    positions: str
    style: str
    image_url: str | None = None


class ThinkerSuggestion(BaseModel):
    """A suggested thinker for a topic."""

    name: str
    reason: str
    profile: ThinkerProfile


class ThinkerSuggestRequest(BaseModel):
    """Request to get thinker suggestions for a topic."""

    topic: str = Field(..., min_length=1)
    count: int = Field(default=3, ge=1, le=5)
    exclude: list[str] = Field(default_factory=list, description="Thinker names to exclude")


class ThinkerValidateRequest(BaseModel):
    """Request to validate a thinker name."""

    name: str = Field(..., min_length=1)


class ThinkerValidateResponse(BaseModel):
    """Response for thinker validation."""

    valid: bool
    name: str
    profile: ThinkerProfile | None = None
    error: str | None = None
