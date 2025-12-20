"""Schemas for spend tracking and limits."""

from pydantic import BaseModel, ConfigDict, Field


class SessionSpend(BaseModel):
    """Spend data for a single session."""

    session_id: str
    total_spend: float = Field(ge=0, description="Total spend for this session")
    conversation_count: int = Field(ge=0, description="Number of conversations in session")


class ConversationSpend(BaseModel):
    """Spend data for a single conversation (thread)."""

    conversation_id: str
    session_id: str
    topic: str
    total_spend: float = Field(ge=0, description="Total spend for this conversation")
    message_count: int = Field(ge=0, description="Number of messages with cost")


class UserSpendData(BaseModel):
    """Complete spend data for a user."""

    model_config = ConfigDict(from_attributes=True)

    user_id: str
    username: str
    total_spend: float = Field(ge=0, description="Total lifetime spend for user")
    sessions: list[SessionSpend] = Field(default_factory=list)
    conversations: list[ConversationSpend] = Field(default_factory=list)
