"""Admin API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_admin
from app.core.database import get_db
from app.models import Conversation, Session, User
from app.schemas import UserWithStats

router = APIRouter()


@router.get("/users", response_model=list[UserWithStats])
async def list_users(
    _: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
) -> list[UserWithStats]:
    """List all users with their stats (admin only)."""
    # Get all users with conversation counts
    result = await db.execute(
        select(
            User,
            func.count(Conversation.id).label("conversation_count"),
        )
        .outerjoin(Session, Session.user_id == User.id)
        .outerjoin(Conversation, Conversation.session_id == Session.id)
        .group_by(User.id)
    )

    users_with_stats = []
    for row in result:
        user = row[0]
        conv_count = row[1] or 0
        users_with_stats.append(
            UserWithStats(
                id=user.id,
                username=user.username,
                display_name=user.display_name,
                is_admin=user.is_admin,
                total_spend=user.total_spend,
                spend_limit=user.spend_limit,
                conversation_count=conv_count,
                created_at=user.created_at,
            )
        )

    return users_with_stats


class UpdateSpendLimitRequest(BaseModel):
    """Request schema for updating spend limit."""

    spend_limit: float = Field(..., gt=0, description="New spend limit in dollars")


class UpdateSpendLimitResponse(BaseModel):
    """Response schema for spend limit update."""

    user_id: str
    spend_limit: float
    message: str


@router.patch("/users/{user_id}/spend-limit", response_model=UpdateSpendLimitResponse)
async def update_spend_limit(
    user_id: str,
    request: UpdateSpendLimitRequest,
    _: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
) -> UpdateSpendLimitResponse:
    """Update a user's spend limit (admin only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user.spend_limit = request.spend_limit
    await db.commit()

    return UpdateSpendLimitResponse(
        user_id=user.id,
        spend_limit=user.spend_limit,
        message=f"Spend limit updated to ${request.spend_limit:.2f}",
    )


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    admin: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Delete a user and all their data (admin only)."""
    # Prevent self-deletion
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )

    # Find the user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Delete the user (cascades to sessions and conversations)
    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()

    return {"message": f"User {user.username} deleted successfully"}
