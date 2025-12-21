"""Pydantic schemas for request/response validation."""

from app.schemas.auth import (
    AuthError,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
    UserWithStats,
)
from app.schemas.conversation import (
    ConversationCreate,
    ConversationResponse,
    ConversationSummary,
    ConversationWithMessages,
)
from app.schemas.message import MessageCreate, MessageResponse
from app.schemas.session import SessionCreate, SessionResponse
from app.schemas.thinker import (
    ThinkerCreate,
    ThinkerProfile,
    ThinkerResponse,
    ThinkerSuggestion,
    ThinkerSuggestRequest,
    ThinkerValidateRequest,
    ThinkerValidateResponse,
)

__all__ = [
    "AuthError",
    "ConversationCreate",
    "ConversationResponse",
    "ConversationSummary",
    "ConversationWithMessages",
    "MessageCreate",
    "MessageResponse",
    "SessionCreate",
    "SessionResponse",
    "ThinkerCreate",
    "ThinkerProfile",
    "ThinkerResponse",
    "ThinkerSuggestion",
    "ThinkerSuggestRequest",
    "ThinkerValidateRequest",
    "ThinkerValidateResponse",
    "TokenResponse",
    "UserLogin",
    "UserRegister",
    "UserResponse",
    "UserWithStats",
]
