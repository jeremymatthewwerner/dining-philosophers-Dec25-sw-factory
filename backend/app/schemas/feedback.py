"""Schemas for feedback endpoints."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class FeedbackType(str, Enum):
    """Type of feedback submitted."""

    BUG = "bug"
    FEATURE = "feature"
    OTHER = "other"


# Max screenshot size: 5MB (base64 is ~33% larger than binary)
MAX_SCREENSHOT_SIZE = 7_000_000  # ~5MB binary = ~6.67MB base64


class FeedbackCreate(BaseModel):
    """Request schema for creating feedback."""

    feedback_type: FeedbackType = Field(default=FeedbackType.BUG)
    message: str = Field(..., min_length=10, max_length=5000)
    email: str | None = Field(default=None, max_length=255)
    name: str | None = Field(default=None, max_length=100)
    user_agent: str | None = Field(default=None, max_length=1000)
    screenshot_data: str | None = Field(default=None, description="Base64 encoded screenshot image")
    screenshot_filename: str | None = Field(default=None, max_length=255)

    @field_validator("screenshot_data")
    @classmethod
    def validate_screenshot_size(cls, v: str | None) -> str | None:
        """Validate that screenshot data is not too large."""
        if v is not None and len(v) > MAX_SCREENSHOT_SIZE:
            raise ValueError("Screenshot is too large. Maximum size is 5MB.")
        return v


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
