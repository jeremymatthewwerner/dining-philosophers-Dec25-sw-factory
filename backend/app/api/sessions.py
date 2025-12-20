"""API routes for session management."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import decode_access_token
from app.core.database import get_db
from app.models import Session, User
from app.schemas import SessionResponse

router = APIRouter()
security = HTTPBearer()


async def get_session_from_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: AsyncSession = Depends(get_db),
) -> Session:
    """Get the session from the JWT token.

    The session_id is encoded in the JWT token when the user logs in.
    """
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="Invalid token - no session")

    result = await db.execute(
        select(Session).where(Session.id == session_id).options(selectinload(Session.user))
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session


async def get_current_user_from_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get the current user from the JWT token."""
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token - no user")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


@router.get("/me", response_model=SessionResponse)
async def get_current_session(
    session: Annotated[Session, Depends(get_session_from_token)],
) -> Session:
    """Get current session from JWT token."""
    return session
