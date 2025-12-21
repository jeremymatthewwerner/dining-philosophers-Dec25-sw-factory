"""Spend tracking API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_admin
from app.core.database import get_db
from app.models import User
from app.schemas.spend import UserSpendData
from app.services.spend import get_user_spend_data

router = APIRouter()


@router.get(
    "/{user_id}",
    response_model=UserSpendData,
    summary="Get user spend data",
    description="Retrieve complete spend data for a user including sessions and conversations. Admin only.",
)
async def get_spend(
    user_id: str,
    _: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
) -> UserSpendData:
    """Get spend data for a specific user.

    Requires admin authentication. Returns detailed spend breakdown
    by session and conversation.
    """
    spend_data = await get_user_spend_data(db, user_id)

    if not spend_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return spend_data
