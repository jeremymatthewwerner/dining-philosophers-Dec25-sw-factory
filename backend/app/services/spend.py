"""Service for spend tracking and retrieval."""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.message import Message
from app.models.session import Session as UserSession
from app.models.user import User
from app.schemas.spend import ConversationSpend, SessionSpend, UserSpendData


@dataclass
class SpendStatus:
    """Status of user's spend relative to their limit."""

    current_spend: float
    spend_limit: float
    is_over_limit: bool
    is_near_limit: bool  # True if at 85% or more of limit
    remaining: float
    percentage_used: float


async def check_spend_limit(db: AsyncSession, user_id: str) -> SpendStatus | None:
    """Check if a user is at or over their spend limit.

    Args:
        db: Async database session
        user_id: ID of the user to check

    Returns:
        SpendStatus with limit information, or None if user not found
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return None

    percentage = (user.total_spend / user.spend_limit * 100) if user.spend_limit > 0 else 100
    remaining = max(0, user.spend_limit - user.total_spend)

    return SpendStatus(
        current_spend=user.total_spend,
        spend_limit=user.spend_limit,
        is_over_limit=user.total_spend >= user.spend_limit,
        is_near_limit=percentage >= 85,
        remaining=remaining,
        percentage_used=min(100, percentage),
    )


async def can_user_spend(db: AsyncSession, user_id: str) -> bool:
    """Quick check if user can make Claude API calls.

    Args:
        db: Async database session
        user_id: ID of the user to check

    Returns:
        True if user is under their spend limit, False otherwise
    """
    status = await check_spend_limit(db, user_id)
    if status is None:
        return False  # User not found, deny
    return not status.is_over_limit


async def get_user_spend_data(db: AsyncSession, user_id: str) -> UserSpendData | None:
    """Retrieve complete spend data for a user.

    Args:
        db: Async database session
        user_id: ID of the user to get spend data for

    Returns:
        UserSpendData with all spend information, or None if user not found
    """
    # Get user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return None

    # Get all sessions for user
    sessions_result = await db.execute(select(UserSession).where(UserSession.user_id == user_id))
    sessions = sessions_result.scalars().all()

    # Get conversation spend data with aggregated message costs
    conversation_spend_query = (
        select(
            Conversation.id.label("conversation_id"),
            Conversation.session_id,
            Conversation.topic,
            func.coalesce(func.sum(Message.cost), 0.0).label("total_spend"),
            func.count(Message.id).filter(Message.cost.isnot(None)).label("message_count"),
        )
        .join(UserSession, Conversation.session_id == UserSession.id)
        .outerjoin(Message, Conversation.id == Message.conversation_id)
        .where(UserSession.user_id == user_id)
        .group_by(Conversation.id, Conversation.session_id, Conversation.topic)
    )

    conv_result = await db.execute(conversation_spend_query)
    conversation_rows = conv_result.all()

    # Build conversation spend list
    conversations = [
        ConversationSpend(
            conversation_id=row.conversation_id,
            session_id=row.session_id,
            topic=row.topic,
            total_spend=float(row.total_spend),
            message_count=int(row.message_count),
        )
        for row in conversation_rows
    ]

    # Aggregate session spend from conversations
    session_spend_map: dict[str, float] = {}
    session_conv_count: dict[str, int] = {}
    for conv in conversations:
        session_spend_map[conv.session_id] = (
            session_spend_map.get(conv.session_id, 0.0) + conv.total_spend
        )
        session_conv_count[conv.session_id] = session_conv_count.get(conv.session_id, 0) + 1

    # Build session spend list
    session_spends = [
        SessionSpend(
            session_id=session.id,
            total_spend=session_spend_map.get(session.id, 0.0),
            conversation_count=session_conv_count.get(session.id, 0),
        )
        for session in sessions
    ]

    return UserSpendData(
        user_id=user.id,
        username=user.username,
        total_spend=user.total_spend,
        sessions=session_spends,
        conversations=conversations,
    )
