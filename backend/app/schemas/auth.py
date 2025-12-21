"""Schemas for authentication endpoints."""

from datetime import datetime

from pydantic import BaseModel, Field


class UserRegister(BaseModel):
    """Request schema for user registration."""

    username: str = Field(..., min_length=3, max_length=50)
    display_name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=6, max_length=100)


class UserLogin(BaseModel):
    """Request schema for user login."""

    username: str
    password: str


class UserResponse(BaseModel):
    """Response schema for user data."""

    id: str
    username: str
    display_name: str | None
    is_admin: bool
    total_spend: float
    spend_limit: float
    created_at: datetime


class UserWithStats(BaseModel):
    """Response schema for user with additional stats (admin view)."""

    id: str
    username: str
    display_name: str | None
    is_admin: bool
    total_spend: float
    spend_limit: float
    conversation_count: int
    created_at: datetime


class TokenResponse(BaseModel):
    """Response schema for authentication token."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class AuthError(BaseModel):
    """Error response for authentication failures."""

    detail: str
