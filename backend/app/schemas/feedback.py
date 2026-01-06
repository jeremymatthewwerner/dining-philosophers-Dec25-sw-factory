"""Schemas for feedback endpoints."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class FeedbackType(str, Enum):
    """Type of feedback submitted."""

    BUG = "bug"
    FEATURE = "feature"
    OTHER = "other"


class FeedbackCreate(BaseModel):
    """Request schema for creating feedback."""

    feedback_type: FeedbackType = Field(default=FeedbackType.BUG)
    message: str = Field(..., min_length=10, max_length=5000)
    email: str | None = Field(default=None, max_length=255)
    name: str | None = Field(default=None, max_length=100)
    user_agent: str | None = Field(default=None, max_length=1000)


class FeedbackResponse(BaseModel):
    """Response schema for feedback submission."""

    id: str
    message: str = "Thank you for your feedback!"


class FeedbackDetail(BaseModel):
    """Response schema for feedback details (admin view)."""

    id: str
    feedback_type: str
    message: str
    email: str | None
    name: str | None
    user_agent: str | None
    status: str
    github_issue_url: str | None
    created_at: datetime
    updated_at: datetime
