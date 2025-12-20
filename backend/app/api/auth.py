"""Authentication API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)
from app.core.database import get_db
from app.models import Session, User
from app.schemas import TokenResponse, UserLogin, UserRegister, UserResponse

router = APIRouter()
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Get the current authenticated user from JWT token.

    Returns None if no valid token is provided.
    """
    if not credentials:
        return None

    payload = decode_access_token(credentials.credentials)
    if not payload:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def require_user(
    user: Annotated[User | None, Depends(get_current_user)],
) -> User:
    """Require an authenticated user, raise 401 if not authenticated."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_admin(
    user: Annotated[User, Depends(require_user)],
) -> User:
    """Require an admin user, raise 403 if not admin."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


@router.post("/register", response_model=TokenResponse)
async def register(
    data: UserRegister,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Register a new user account."""
    # Check if username already exists
    result = await db.execute(select(User).where(User.username == data.username))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken",
        )

    # Create new user
    password_hash = get_password_hash(data.password)
    user = User(
        username=data.username,
        display_name=data.display_name,
        password_hash=password_hash,
    )
    db.add(user)
    await db.flush()  # Generate user.id

    # Create a default session for the user
    session = Session(user_id=user.id)
    db.add(session)
    await db.flush()  # Generate session.id
    await db.refresh(user)

    # Create access token
    access_token = create_access_token(data={"sub": user.id, "session_id": session.id})

    return TokenResponse(
        access_token=access_token,
        user=UserResponse(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            is_admin=user.is_admin,
            total_spend=user.total_spend,
            spend_limit=user.spend_limit,
            created_at=user.created_at,
        ),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    data: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Login with username and password."""
    # Find user by username
    result = await db.execute(select(User).where(User.username == data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Get or create session for this login
    sessions_result = await db.execute(select(Session).where(Session.user_id == user.id))
    session = sessions_result.scalars().first()

    if not session:
        session = Session(user_id=user.id)
        db.add(session)
        await db.commit()
        await db.refresh(session)

    # Create access token
    access_token = create_access_token(data={"sub": user.id, "session_id": session.id})

    return TokenResponse(
        access_token=access_token,
        user=UserResponse(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            is_admin=user.is_admin,
            total_spend=user.total_spend,
            spend_limit=user.spend_limit,
            created_at=user.created_at,
        ),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    user: Annotated[User, Depends(require_user)],
) -> UserResponse:
    """Get the current authenticated user."""
    return UserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        is_admin=user.is_admin,
        total_spend=user.total_spend,
        spend_limit=user.spend_limit,
        created_at=user.created_at,
    )


@router.post("/logout")
async def logout() -> dict[str, str]:
    """Logout the current user.

    Note: Since we use JWT tokens, logout is handled client-side
    by removing the token. This endpoint is provided for completeness.
    """
    return {"message": "Logged out successfully"}
