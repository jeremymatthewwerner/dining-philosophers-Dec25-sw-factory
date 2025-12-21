"""WebSocket handler for real-time chat messaging."""

import asyncio
import json
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Conversation, Message, User
from app.models.message import SenderType

if TYPE_CHECKING:
    pass

router = APIRouter()


class WSMessageType(str, Enum):
    """Types of WebSocket messages."""

    # Client -> Server
    JOIN = "join"
    LEAVE = "leave"
    USER_MESSAGE = "user_message"
    TYPING_START = "typing_start"
    TYPING_STOP = "typing_stop"
    PAUSE = "pause"
    RESUME = "resume"
    SET_SPEED = "set_speed"  # Set conversation speed multiplier

    # Server -> Client
    MESSAGE = "message"
    THINKER_TYPING = "thinker_typing"
    THINKER_THINKING = "thinker_thinking"  # Shows what thinker is thinking about
    THINKER_STOPPED_TYPING = "thinker_stopped_typing"
    USER_JOINED = "user_joined"
    USER_LEFT = "user_left"
    PAUSED = "paused"
    RESUMED = "resumed"
    SPEED_CHANGED = "speed_changed"  # Notify clients of speed change
    ERROR = "error"


class WSMessage(BaseModel):
    """WebSocket message structure."""

    type: WSMessageType
    conversation_id: str | None = None
    content: str | None = None
    sender_name: str | None = None
    sender_type: str | None = None
    message_id: str | None = None
    timestamp: str | None = None
    cost: float | None = None
    speed_multiplier: float | None = None  # For speed control (0.5 to 3.0)


@dataclass
class ConversationRoom:
    """Manages WebSocket connections for a conversation."""

    conversation_id: str
    connections: set[WebSocket] = field(default_factory=set)
    is_active: bool = False
    typing_thinkers: set[str] = field(default_factory=set)
    speed_multiplier: float = 1.0  # 1.0 = normal, 0.5 = fast, 2.0+ = slow

    def add_connection(self, websocket: WebSocket) -> None:
        """Add a WebSocket connection to the room."""
        self.connections.add(websocket)
        self.is_active = True

    def remove_connection(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from the room."""
        self.connections.discard(websocket)
        if not self.connections:
            self.is_active = False

    async def broadcast(self, message: WSMessage) -> None:
        """Broadcast a message to all connected clients."""
        message_data = message.model_dump_json()
        disconnected = set()
        for connection in self.connections:
            try:
                await connection.send_text(message_data)
            except Exception:
                disconnected.add(connection)
        # Clean up disconnected clients
        for conn in disconnected:
            self.connections.discard(conn)
        if not self.connections:
            self.is_active = False


class ConnectionManager:
    """Manages all WebSocket connections across conversations."""

    def __init__(self) -> None:
        self.rooms: dict[str, ConversationRoom] = defaultdict(
            lambda: ConversationRoom(conversation_id="")
        )
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, conversation_id: str) -> None:
        """Accept a new WebSocket connection and add to room."""
        await websocket.accept()
        async with self._lock:
            if conversation_id not in self.rooms:
                self.rooms[conversation_id] = ConversationRoom(conversation_id=conversation_id)
            self.rooms[conversation_id].add_connection(websocket)

    async def disconnect(self, websocket: WebSocket, conversation_id: str) -> None:
        """Remove a WebSocket connection from its room."""
        async with self._lock:
            if conversation_id in self.rooms:
                self.rooms[conversation_id].remove_connection(websocket)

    def is_conversation_active(self, conversation_id: str) -> bool:
        """Check if a conversation has any active connections."""
        return conversation_id in self.rooms and self.rooms[conversation_id].is_active

    def get_speed_multiplier(self, conversation_id: str) -> float:
        """Get the speed multiplier for a conversation (1.0 = normal)."""
        if conversation_id in self.rooms:
            return self.rooms[conversation_id].speed_multiplier
        return 1.0

    async def set_speed_multiplier(self, conversation_id: str, multiplier: float) -> None:
        """Set the speed multiplier for a conversation (0.5 to 6.0)."""
        # Clamp to valid range (6x for very slow, contemplative pace)
        multiplier = max(0.5, min(6.0, multiplier))
        if conversation_id in self.rooms:
            self.rooms[conversation_id].speed_multiplier = multiplier
            # Notify all clients of the speed change
            await self.broadcast_to_conversation(
                conversation_id,
                WSMessage(
                    type=WSMessageType.SPEED_CHANGED,
                    conversation_id=conversation_id,
                    speed_multiplier=multiplier,
                ),
            )

    async def broadcast_to_conversation(self, conversation_id: str, message: WSMessage) -> None:
        """Broadcast a message to all connections in a conversation."""
        if conversation_id in self.rooms:
            await self.rooms[conversation_id].broadcast(message)

    async def send_thinker_message(
        self,
        conversation_id: str,
        thinker_name: str,
        content: str,
        message_id: str,
        cost: float | None = None,
    ) -> None:
        """Send a thinker's message to the conversation."""
        message = WSMessage(
            type=WSMessageType.MESSAGE,
            conversation_id=conversation_id,
            sender_type="thinker",
            sender_name=thinker_name,
            content=content,
            message_id=message_id,
            timestamp=datetime.now(UTC).isoformat(),
            cost=cost,
        )
        await self.broadcast_to_conversation(conversation_id, message)

    async def send_thinker_typing(self, conversation_id: str, thinker_name: str) -> None:
        """Notify that a thinker is typing."""
        if conversation_id in self.rooms:
            self.rooms[conversation_id].typing_thinkers.add(thinker_name)
        message = WSMessage(
            type=WSMessageType.THINKER_TYPING,
            conversation_id=conversation_id,
            sender_name=thinker_name,
        )
        await self.broadcast_to_conversation(conversation_id, message)

    async def send_thinker_thinking(
        self, conversation_id: str, thinker_name: str, thinking_content: str
    ) -> None:
        """Send what a thinker is thinking about (displayed instead of just 'Thinking...')."""
        message = WSMessage(
            type=WSMessageType.THINKER_THINKING,
            conversation_id=conversation_id,
            sender_name=thinker_name,
            content=thinking_content,
        )
        await self.broadcast_to_conversation(conversation_id, message)

    async def send_thinker_stopped_typing(self, conversation_id: str, thinker_name: str) -> None:
        """Notify that a thinker stopped typing."""
        if conversation_id in self.rooms:
            self.rooms[conversation_id].typing_thinkers.discard(thinker_name)
        message = WSMessage(
            type=WSMessageType.THINKER_STOPPED_TYPING,
            conversation_id=conversation_id,
            sender_name=thinker_name,
        )
        await self.broadcast_to_conversation(conversation_id, message)


# Global connection manager
manager = ConnectionManager()


async def get_messages_for_conversation(
    conversation_id: str, db: AsyncSession
) -> Sequence[Message]:
    """Get all messages for a conversation."""
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    return result.scalars().all()


class SpendLimitExceeded(Exception):
    """Raised when a user exceeds their spend limit."""

    def __init__(self, current_spend: float, spend_limit: float) -> None:
        self.current_spend = current_spend
        self.spend_limit = spend_limit
        super().__init__(f"Spend limit exceeded: ${current_spend:.2f} / ${spend_limit:.2f}")


async def save_thinker_message(
    conversation_id: str, thinker_name: str, content: str, cost: float, db: AsyncSession
) -> Message:
    """Save a thinker's message to the database and update user's total spend.

    Raises:
        SpendLimitExceeded: If the user has reached their spend limit
    """
    # Update the user's total_spend by traversing the relationship chain
    # Conversation -> Session -> User
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .options(selectinload(Conversation.session))
    )
    conversation = result.scalar_one_or_none()

    user = None
    if conversation and conversation.session:
        # Get the user and check spend limit BEFORE creating message
        user_result = await db.execute(select(User).where(User.id == conversation.session.user_id))
        user = user_result.scalar_one_or_none()

        if user and user.total_spend >= user.spend_limit:
            raise SpendLimitExceeded(user.total_spend, user.spend_limit)

    # Create and save the message
    message = Message(
        conversation_id=conversation_id,
        sender_type=SenderType.THINKER,
        sender_name=thinker_name,
        content=content,
        cost=cost,
    )
    db.add(message)

    # Update user's total spend
    if user:
        user.total_spend += cost

    await db.commit()
    await db.refresh(message)
    return message


@router.websocket("/ws/{conversation_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    conversation_id: str,
    token: str | None = None,
) -> None:
    """WebSocket endpoint for real-time chat messaging.

    Clients connect to this endpoint to receive real-time updates about:
    - New messages from thinkers
    - Typing indicators
    - User join/leave events

    Authentication is done via the 'token' query parameter.
    """
    # Import here to avoid circular imports
    from app.core.auth import decode_access_token
    from app.services.thinker import thinker_service

    # Validate token
    if not token:
        await websocket.close(code=4001, reason="Authentication required")
        return

    payload = decode_access_token(token)
    if not payload:
        await websocket.close(code=4001, reason="Invalid token")
        return

    session_id = payload.get("session_id")
    if not session_id:
        await websocket.close(code=4001, reason="Invalid token - no session")
        return

    await manager.connect(websocket, conversation_id)

    # Notify others that a user joined
    await manager.broadcast_to_conversation(
        conversation_id,
        WSMessage(
            type=WSMessageType.USER_JOINED,
            conversation_id=conversation_id,
        ),
    )

    # Send current pause state to the newly connected client
    if thinker_service.is_paused(conversation_id):
        await websocket.send_text(
            WSMessage(
                type=WSMessageType.PAUSED,
                conversation_id=conversation_id,
            ).model_dump_json()
        )

    # Get the conversation and start thinker agents
    # We need to create a new db session for the agent callbacks
    from app.core.database import async_session_maker

    async with async_session_maker() as db:
        # Load conversation with thinkers
        result = await db.execute(
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .options(selectinload(Conversation.thinkers))
        )
        conversation = result.scalar_one_or_none()

        if conversation and conversation.thinkers:
            # Create callback functions that use their own db sessions
            async def get_messages(conv_id: str) -> Sequence[Message]:
                async with async_session_maker() as session:
                    return await get_messages_for_conversation(conv_id, session)

            async def save_message(
                conv_id: str, thinker_name: str, content: str, cost: float
            ) -> Message:
                async with async_session_maker() as session:
                    return await save_thinker_message(conv_id, thinker_name, content, cost, session)

            # Start thinker agents
            await thinker_service.start_conversation_agents(
                conversation_id,
                list(conversation.thinkers),
                conversation.topic,
                get_messages,
                save_message,
            )

    try:
        while True:
            # Receive and parse message from client
            data = await websocket.receive_text()
            try:
                message_data = json.loads(data)
                message_type = message_data.get("type")

                if message_type == WSMessageType.TYPING_START:
                    # User started typing - could be used to pause thinkers
                    pass
                elif message_type == WSMessageType.TYPING_STOP:
                    # User stopped typing
                    pass
                elif message_type == WSMessageType.PAUSE.value:
                    # Pause thinker agents
                    thinker_service.pause_conversation(conversation_id)
                    await manager.broadcast_to_conversation(
                        conversation_id,
                        WSMessage(
                            type=WSMessageType.PAUSED,
                            conversation_id=conversation_id,
                        ),
                    )
                elif message_type == WSMessageType.RESUME.value:
                    # Resume thinker agents
                    thinker_service.resume_conversation(conversation_id)
                    await manager.broadcast_to_conversation(
                        conversation_id,
                        WSMessage(
                            type=WSMessageType.RESUMED,
                            conversation_id=conversation_id,
                        ),
                    )
                elif message_type == WSMessageType.SET_SPEED.value:
                    # Set conversation speed multiplier
                    speed = message_data.get("speed_multiplier", 1.0)
                    await manager.set_speed_multiplier(conversation_id, float(speed))
                elif message_type == WSMessageType.USER_MESSAGE:
                    # User sent a message - broadcast to all
                    # Note: The actual message storage is handled by the REST API
                    # This is just for real-time notification
                    content = message_data.get("content", "")
                    await manager.broadcast_to_conversation(
                        conversation_id,
                        WSMessage(
                            type=WSMessageType.MESSAGE,
                            conversation_id=conversation_id,
                            sender_type="user",
                            content=content,
                            timestamp=datetime.now(UTC).isoformat(),
                        ),
                    )
            except json.JSONDecodeError:
                await websocket.send_text(
                    WSMessage(
                        type=WSMessageType.ERROR,
                        content="Invalid JSON",
                    ).model_dump_json()
                )

    except WebSocketDisconnect:
        await manager.disconnect(websocket, conversation_id)
        # Stop thinker agents when user disconnects
        await thinker_service.stop_conversation_agents(conversation_id)
        # Notify others that a user left
        await manager.broadcast_to_conversation(
            conversation_id,
            WSMessage(
                type=WSMessageType.USER_LEFT,
                conversation_id=conversation_id,
            ),
        )
