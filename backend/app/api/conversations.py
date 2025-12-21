"""API routes for conversation management."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.sessions import get_session_from_token
from app.core.database import get_db
from app.models import Conversation, ConversationThinker, Message, Session
from app.models.message import SenderType
from app.schemas import (
    ConversationCreate,
    ConversationResponse,
    ConversationSummary,
    ConversationWithMessages,
    MessageCreate,
    MessageResponse,
)

router = APIRouter()


@router.post("", response_model=ConversationResponse)
async def create_conversation(
    data: ConversationCreate,
    session: Annotated[Session, Depends(get_session_from_token)],
    db: AsyncSession = Depends(get_db),
) -> Conversation:
    """Create a new conversation with thinkers."""
    # Create conversation
    conversation = Conversation(
        session_id=session.id,
        topic=data.topic,
    )
    db.add(conversation)
    await db.flush()

    # Add thinkers to conversation
    colors = ["#6366f1", "#ec4899", "#10b981", "#f59e0b", "#8b5cf6"]
    for i, thinker_data in enumerate(data.thinkers):
        thinker = ConversationThinker(
            conversation_id=conversation.id,
            name=thinker_data.name,
            bio=thinker_data.bio,
            positions=thinker_data.positions,
            style=thinker_data.style,
            color=thinker_data.color
            if thinker_data.color != "#6366f1"
            else colors[i % len(colors)],
            image_url=thinker_data.image_url,
        )
        db.add(thinker)

    await db.flush()

    # Reload with thinkers
    await db.refresh(conversation, attribute_names=["thinkers"])
    return conversation


@router.get("", response_model=list[ConversationSummary])
async def list_conversations(
    session: Annotated[Session, Depends(get_session_from_token)],
    db: AsyncSession = Depends(get_db),
) -> list[ConversationSummary]:
    """List all conversations for the current session with message counts."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.session_id == session.id)
        .options(
            selectinload(Conversation.thinkers),
            selectinload(Conversation.messages),
        )
        .order_by(Conversation.created_at.desc())
    )
    conversations = result.scalars().all()

    # Build summaries with message counts and costs
    summaries = []
    for conv in conversations:
        total_cost = sum(msg.cost or 0.0 for msg in conv.messages)
        summaries.append(
            ConversationSummary(
                id=conv.id,
                session_id=conv.session_id,
                topic=conv.topic,
                title=conv.title,
                is_active=conv.is_active,
                created_at=conv.created_at,
                # Pydantic handles ORM model -> schema conversion via from_attributes=True
                thinkers=conv.thinkers,  # type: ignore[arg-type]
                message_count=len(conv.messages),
                total_cost=total_cost,
            )
        )
    return summaries


@router.get("/{conversation_id}", response_model=ConversationWithMessages)
async def get_conversation(
    conversation_id: str,
    session: Annotated[Session, Depends(get_session_from_token)],
    db: AsyncSession = Depends(get_db),
) -> Conversation:
    """Get a conversation with its messages."""
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.id == conversation_id,
            Conversation.session_id == session.id,
        )
        .options(
            selectinload(Conversation.thinkers),
            selectinload(Conversation.messages),
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    session: Annotated[Session, Depends(get_session_from_token)],
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Delete a conversation and all its messages."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.session_id == session.id,
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await db.delete(conversation)
    await db.flush()
    return {"status": "deleted"}


@router.post("/{conversation_id}/messages", response_model=MessageResponse)
async def send_message(
    conversation_id: str,
    data: MessageCreate,
    session: Annotated[Session, Depends(get_session_from_token)],
    db: AsyncSession = Depends(get_db),
) -> Message:
    """Send a user message to a conversation."""
    # Verify conversation exists and belongs to session
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.session_id == session.id,
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Create message with user's display name
    user = session.user
    sender_name = user.display_name or user.username
    message = Message(
        conversation_id=conversation_id,
        sender_type=SenderType.USER,
        sender_name=sender_name,
        content=data.content,
    )
    db.add(message)
    await db.flush()

    return message
