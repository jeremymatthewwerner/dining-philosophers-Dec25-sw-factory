"""Tests for spend tracking service."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.message import Message, SenderType
from app.models.session import Session as UserSession
from app.models.user import User
from app.services.spend import can_user_spend, check_spend_limit, get_user_spend_data


@pytest.mark.asyncio
async def test_get_user_spend_data_user_not_found(db_session: AsyncSession) -> None:
    """Test that None is returned when user doesn't exist."""
    result = await get_user_spend_data(db_session, "nonexistent-user-id")
    assert result is None


@pytest.mark.asyncio
async def test_get_user_spend_data_user_with_no_sessions(
    db_session: AsyncSession,
) -> None:
    """Test user with no sessions returns empty lists."""
    # Create a user with no sessions
    user = User(
        id="user-1",
        username="testuser",
        password_hash="hash",
        total_spend=0.0,
    )
    db_session.add(user)
    await db_session.commit()

    result = await get_user_spend_data(db_session, "user-1")

    assert result is not None
    assert result.user_id == "user-1"
    assert result.username == "testuser"
    assert result.total_spend == 0.0
    assert result.sessions == []
    assert result.conversations == []


@pytest.mark.asyncio
async def test_get_user_spend_data_user_with_sessions_no_conversations(
    db_session: AsyncSession,
) -> None:
    """Test user with sessions but no conversations."""
    # Create user and session
    user = User(
        id="user-1",
        username="testuser",
        password_hash="hash",
        total_spend=0.0,
    )
    session = UserSession(id="session-1", user_id="user-1")
    db_session.add_all([user, session])
    await db_session.commit()

    result = await get_user_spend_data(db_session, "user-1")

    assert result is not None
    assert len(result.sessions) == 1
    assert result.sessions[0].session_id == "session-1"
    assert result.sessions[0].total_spend == 0.0
    assert result.sessions[0].conversation_count == 0
    assert result.conversations == []


@pytest.mark.asyncio
async def test_get_user_spend_data_user_with_conversations_no_messages(
    db_session: AsyncSession,
) -> None:
    """Test user with conversations but no messages."""
    # Create user, session, and conversation
    user = User(
        id="user-1",
        username="testuser",
        password_hash="hash",
        total_spend=0.0,
    )
    session = UserSession(id="session-1", user_id="user-1")
    conversation = Conversation(
        id="conv-1",
        session_id="session-1",
        topic="Test topic",
    )
    db_session.add_all([user, session, conversation])
    await db_session.commit()

    result = await get_user_spend_data(db_session, "user-1")

    assert result is not None
    assert len(result.sessions) == 1
    assert result.sessions[0].conversation_count == 1
    assert len(result.conversations) == 1
    assert result.conversations[0].conversation_id == "conv-1"
    assert result.conversations[0].topic == "Test topic"
    assert result.conversations[0].total_spend == 0.0
    assert result.conversations[0].message_count == 0


@pytest.mark.asyncio
async def test_get_user_spend_data_with_message_costs(
    db_session: AsyncSession,
) -> None:
    """Test user with messages that have costs."""
    # Create full hierarchy with costs
    user = User(
        id="user-1",
        username="testuser",
        password_hash="hash",
        total_spend=0.35,  # Should match sum of message costs
    )
    session = UserSession(id="session-1", user_id="user-1")
    conversation = Conversation(
        id="conv-1",
        session_id="session-1",
        topic="Test topic",
    )
    message1 = Message(
        id="msg-1",
        conversation_id="conv-1",
        sender_type=SenderType.THINKER,
        sender_name="Einstein",
        content="E=mc²",
        cost=0.15,
    )
    message2 = Message(
        id="msg-2",
        conversation_id="conv-1",
        sender_type=SenderType.THINKER,
        sender_name="Newton",
        content="F=ma",
        cost=0.20,
    )
    # Message without cost (user message)
    message3 = Message(
        id="msg-3",
        conversation_id="conv-1",
        sender_type=SenderType.USER,
        content="Hello",
        cost=None,
    )
    db_session.add_all([user, session, conversation, message1, message2, message3])
    await db_session.commit()

    result = await get_user_spend_data(db_session, "user-1")

    assert result is not None
    assert result.total_spend == 0.35
    assert len(result.conversations) == 1
    assert result.conversations[0].total_spend == 0.35
    assert result.conversations[0].message_count == 2  # Only messages with cost
    assert result.sessions[0].total_spend == 0.35


@pytest.mark.asyncio
async def test_get_user_spend_data_multiple_sessions_and_conversations(
    db_session: AsyncSession,
) -> None:
    """Test user with multiple sessions and conversations."""
    user = User(
        id="user-1",
        username="testuser",
        password_hash="hash",
        total_spend=1.0,
    )
    session1 = UserSession(id="session-1", user_id="user-1")
    session2 = UserSession(id="session-2", user_id="user-1")
    conv1 = Conversation(id="conv-1", session_id="session-1", topic="Topic 1")
    conv2 = Conversation(id="conv-2", session_id="session-1", topic="Topic 2")
    conv3 = Conversation(id="conv-3", session_id="session-2", topic="Topic 3")

    msg1 = Message(
        id="msg-1",
        conversation_id="conv-1",
        sender_type=SenderType.THINKER,
        content="Hello",
        cost=0.30,
    )
    msg2 = Message(
        id="msg-2",
        conversation_id="conv-2",
        sender_type=SenderType.THINKER,
        content="World",
        cost=0.20,
    )
    msg3 = Message(
        id="msg-3",
        conversation_id="conv-3",
        sender_type=SenderType.THINKER,
        content="Test",
        cost=0.50,
    )

    db_session.add_all([user, session1, session2, conv1, conv2, conv3, msg1, msg2, msg3])
    await db_session.commit()

    result = await get_user_spend_data(db_session, "user-1")

    assert result is not None
    assert result.total_spend == 1.0
    assert len(result.sessions) == 2
    assert len(result.conversations) == 3

    # Check session aggregation
    session1_data = next(s for s in result.sessions if s.session_id == "session-1")
    session2_data = next(s for s in result.sessions if s.session_id == "session-2")

    assert session1_data.total_spend == 0.50  # conv1 + conv2
    assert session1_data.conversation_count == 2
    assert session2_data.total_spend == 0.50  # conv3
    assert session2_data.conversation_count == 1


# Spend limit checking tests


@pytest.mark.asyncio
async def test_check_spend_limit_user_not_found(db_session: AsyncSession) -> None:
    """Test check_spend_limit returns None for non-existent user."""
    result = await check_spend_limit(db_session, "nonexistent-user")
    assert result is None


@pytest.mark.asyncio
async def test_check_spend_limit_under_limit(db_session: AsyncSession) -> None:
    """Test user under spend limit."""
    user = User(
        id="user-1",
        username="testuser",
        password_hash="hash",
        total_spend=5.0,
        spend_limit=10.0,
    )
    db_session.add(user)
    await db_session.commit()

    result = await check_spend_limit(db_session, "user-1")

    assert result is not None
    assert result.current_spend == 5.0
    assert result.spend_limit == 10.0
    assert result.is_over_limit is False
    assert result.is_near_limit is False
    assert result.remaining == 5.0
    assert result.percentage_used == 50.0


@pytest.mark.asyncio
async def test_check_spend_limit_at_limit(db_session: AsyncSession) -> None:
    """Test user at exactly their spend limit."""
    user = User(
        id="user-1",
        username="testuser",
        password_hash="hash",
        total_spend=10.0,
        spend_limit=10.0,
    )
    db_session.add(user)
    await db_session.commit()

    result = await check_spend_limit(db_session, "user-1")

    assert result is not None
    assert result.is_over_limit is True
    assert result.is_near_limit is True
    assert result.remaining == 0.0
    assert result.percentage_used == 100.0


@pytest.mark.asyncio
async def test_check_spend_limit_over_limit(db_session: AsyncSession) -> None:
    """Test user over their spend limit."""
    user = User(
        id="user-1",
        username="testuser",
        password_hash="hash",
        total_spend=15.0,
        spend_limit=10.0,
    )
    db_session.add(user)
    await db_session.commit()

    result = await check_spend_limit(db_session, "user-1")

    assert result is not None
    assert result.is_over_limit is True
    assert result.is_near_limit is True
    assert result.remaining == 0.0
    assert result.percentage_used == 100.0  # Capped at 100


@pytest.mark.asyncio
async def test_check_spend_limit_near_limit(db_session: AsyncSession) -> None:
    """Test user near (85%+) their spend limit."""
    user = User(
        id="user-1",
        username="testuser",
        password_hash="hash",
        total_spend=8.5,
        spend_limit=10.0,
    )
    db_session.add(user)
    await db_session.commit()

    result = await check_spend_limit(db_session, "user-1")

    assert result is not None
    assert result.is_over_limit is False
    assert result.is_near_limit is True
    assert result.remaining == 1.5
    assert result.percentage_used == 85.0


@pytest.mark.asyncio
async def test_can_user_spend_under_limit(db_session: AsyncSession) -> None:
    """Test can_user_spend returns True when under limit."""
    user = User(
        id="user-1",
        username="testuser",
        password_hash="hash",
        total_spend=5.0,
        spend_limit=10.0,
    )
    db_session.add(user)
    await db_session.commit()

    result = await can_user_spend(db_session, "user-1")
    assert result is True


@pytest.mark.asyncio
async def test_can_user_spend_at_limit(db_session: AsyncSession) -> None:
    """Test can_user_spend returns False when at limit."""
    user = User(
        id="user-1",
        username="testuser",
        password_hash="hash",
        total_spend=10.0,
        spend_limit=10.0,
    )
    db_session.add(user)
    await db_session.commit()

    result = await can_user_spend(db_session, "user-1")
    assert result is False


@pytest.mark.asyncio
async def test_can_user_spend_user_not_found(db_session: AsyncSession) -> None:
    """Test can_user_spend returns False for non-existent user."""
    result = await can_user_spend(db_session, "nonexistent-user")
    assert result is False
