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
    ThinkerCreate,
    ThinkerResponse,
)

router = APIRouter()


@router.post("", response_model=ConversationResponse)
async def create_conversation(
    data: ConversationCreate,
    session: Annotated[Session, Depends(get_session_from_token)],
    db: AsyncSession = Depends(get_db),
) -> Conversation:
    """Create a new conversation with thinkers."""
    from app.services.knowledge_research import knowledge_service

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
        # Trigger background knowledge research for each thinker
        knowledge_service.trigger_research(thinker_data.name)

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


@router.put("/{conversation_id}/thinkers", response_model=list[ThinkerResponse])
async def add_thinkers_to_conversation(
    conversation_id: str,
    thinkers: list[ThinkerCreate],
    session: Annotated[Session, Depends(get_session_from_token)],
    db: AsyncSession = Depends(get_db),
) -> list[ConversationThinker]:
    """Add one or more thinkers to an existing conversation."""
    from app.services.knowledge_research import knowledge_service

    # Verify conversation exists and belongs to session
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.id == conversation_id,
            Conversation.session_id == session.id,
        )
        .options(selectinload(Conversation.thinkers))
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check max thinkers limit (5 total)
    existing_count = len(conversation.thinkers)
    if existing_count + len(thinkers) > 5:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot add {len(thinkers)} thinkers. "
            f"Conversation has {existing_count}/5 thinkers. "
            f"Maximum is 5 total.",
        )

    # Get existing colors to avoid duplicates
    existing_colors = {t.color for t in conversation.thinkers}
    all_colors = ["#6366f1", "#ec4899", "#10b981", "#f59e0b", "#8b5cf6"]
    available_colors = [c for c in all_colors if c not in existing_colors]

    # Add new thinkers
    new_thinkers = []
    for thinker_data in thinkers:
        # Use provided color or pick from available
        color = thinker_data.color
        if color == "#6366f1" and available_colors:
            color = available_colors.pop(0)

        thinker = ConversationThinker(
            conversation_id=conversation_id,
            name=thinker_data.name,
            bio=thinker_data.bio,
            positions=thinker_data.positions,
            style=thinker_data.style,
            color=color,
            image_url=thinker_data.image_url,
        )
        db.add(thinker)
        new_thinkers.append(thinker)
        # Trigger background knowledge research
        knowledge_service.trigger_research(thinker_data.name)

    await db.flush()

    # Refresh to get IDs and timestamps
    for thinker in new_thinkers:
        await db.refresh(thinker)

    return new_thinkers


@router.post("/{conversation_id}/messages", response_model=MessageResponse)
async def send_message(
    conversation_id: str,
    data: MessageCreate,
    session: Annotated[Session, Depends(get_session_from_token)],
    db: AsyncSession = Depends(get_db),
) -> Message:
    """Send a user message to a conversation."""
    from app.api.websocket import WSMessage, WSMessageType, manager
    from app.services.thinker import thinker_service

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

    # Auto-resume if conversation was paused due to idle timeout
    if thinker_service.is_idle_paused(conversation_id):
        thinker_service.resume_from_idle(conversation_id)
        await manager.broadcast_to_conversation(
            conversation_id,
            WSMessage(
                type=WSMessageType.RESUMED,
                conversation_id=conversation_id,
            ),
        )

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
