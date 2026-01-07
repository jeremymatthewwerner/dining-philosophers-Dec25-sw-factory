"""DevOps API endpoints for autonomous agent maintenance operations.

These endpoints are protected by DEVOPS_API_SECRET header authentication
and used by the DevOps agent to perform maintenance tasks.

See REQUIREMENTS.md Section 7 for the full Admin API specification.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models import Conversation, ConversationThinker, Message, Session, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/devops")


# ============================================================================
# Authentication
# ============================================================================


async def require_devops_secret(
    x_devops_secret: Annotated[str | None, Header()] = None,
) -> None:
    """Require valid DevOps API secret in X-DevOps-Secret header."""
    settings = get_settings()

    if not settings.devops_api_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DevOps API not configured (DEVOPS_API_SECRET not set)",
        )

    if not x_devops_secret or x_devops_secret != settings.devops_api_secret:
        logger.warning("DevOps API access denied: invalid or missing secret")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing X-DevOps-Secret header",
        )


# ============================================================================
# Response Schemas
# ============================================================================


class StatsResponse(BaseModel):
    """Database statistics response."""

    users: int
    sessions: int
    conversations: int
    messages: int
    thinkers: int
    timestamp: datetime


class CleanupResponse(BaseModel):
    """Cleanup operation response."""

    deleted_count: int
    details: dict[str, int] | None = None
    dry_run: bool = False


class AuditLogEntry(BaseModel):
    """Audit log entry for admin operations."""

    timestamp: datetime
    action: str
    details: dict[str, str | int | None]


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    _: Annotated[None, Depends(require_devops_secret)],
    db: AsyncSession = Depends(get_db),
) -> StatsResponse:
    """Get database statistics for diagnostics.

    Returns counts of all major entities in the database.
    Useful for monitoring and debugging.
    """
    # Get counts for each table
    users_result = await db.execute(select(func.count(User.id)))
    sessions_result = await db.execute(select(func.count(Session.id)))
    conversations_result = await db.execute(select(func.count(Conversation.id)))
    messages_result = await db.execute(select(func.count(Message.id)))
    thinkers_result = await db.execute(select(func.count(ConversationThinker.id)))

    return StatsResponse(
        users=users_result.scalar() or 0,
        sessions=sessions_result.scalar() or 0,
        conversations=conversations_result.scalar() or 0,
        messages=messages_result.scalar() or 0,
        thinkers=thinkers_result.scalar() or 0,
        timestamp=datetime.now(UTC),
    )


@router.delete("/cleanup/stale-sessions", response_model=CleanupResponse)
async def cleanup_stale_sessions(
    _: Annotated[None, Depends(require_devops_secret)],
    db: AsyncSession = Depends(get_db),
    older_than_hours: int = Query(
        default=24 * 7, ge=1, description="Delete sessions older than N hours"
    ),
    dry_run: bool = Query(default=False, description="Preview without deleting"),
) -> CleanupResponse:
    """Delete sessions older than the specified threshold.

    Sessions are the intermediate layer between users and conversations.
    Old sessions without recent activity can be cleaned up.

    Args:
        older_than_hours: Delete sessions older than this many hours (default: 7 days)
        dry_run: If true, only count without deleting
    """
    cutoff = datetime.now(UTC) - timedelta(hours=older_than_hours)

    # Count sessions to delete
    count_result = await db.execute(
        select(func.count(Session.id)).where(Session.created_at < cutoff)
    )
    count = count_result.scalar() or 0

    if dry_run:
        logger.info(f"[DRY RUN] Would delete {count} sessions older than {cutoff}")
        return CleanupResponse(deleted_count=count, dry_run=True)

    if count > 0:
        await db.execute(delete(Session).where(Session.created_at < cutoff))
        await db.commit()
        logger.info(f"Deleted {count} stale sessions older than {cutoff}")

    return CleanupResponse(deleted_count=count)


@router.delete("/cleanup/orphans", response_model=CleanupResponse)
async def cleanup_orphans(
    _: Annotated[None, Depends(require_devops_secret)],
    db: AsyncSession = Depends(get_db),
    dry_run: bool = Query(default=False, description="Preview without deleting"),
) -> CleanupResponse:
    """Delete orphaned records (conversations without sessions, etc.).

    Finds and removes data that has become orphaned due to cascade failures
    or other issues. This includes:
    - Conversations with no associated session
    - Messages with no associated conversation
    """
    details: dict[str, int] = {}

    # Find orphaned conversations (session_id references non-existent session)
    # Using raw SQL for the subquery approach
    orphan_convs_result = await db.execute(
        text("""
            SELECT COUNT(*) FROM conversations c
            WHERE NOT EXISTS (SELECT 1 FROM sessions s WHERE s.id = c.session_id)
        """)
    )
    orphan_convs = orphan_convs_result.scalar() or 0
    details["orphan_conversations"] = orphan_convs

    # Find orphaned messages
    orphan_msgs_result = await db.execute(
        text("""
            SELECT COUNT(*) FROM messages m
            WHERE NOT EXISTS (SELECT 1 FROM conversations c WHERE c.id = m.conversation_id)
        """)
    )
    orphan_msgs = orphan_msgs_result.scalar() or 0
    details["orphan_messages"] = orphan_msgs

    total = orphan_convs + orphan_msgs

    if dry_run:
        logger.info(f"[DRY RUN] Would delete {total} orphaned records: {details}")
        return CleanupResponse(deleted_count=total, details=details, dry_run=True)

    # Delete orphans (order matters due to foreign keys)
    if orphan_msgs > 0:
        await db.execute(
            text("""
                DELETE FROM messages
                WHERE NOT EXISTS (SELECT 1 FROM conversations c WHERE c.id = messages.conversation_id)
            """)
        )

    if orphan_convs > 0:
        await db.execute(
            text("""
                DELETE FROM conversations
                WHERE NOT EXISTS (SELECT 1 FROM sessions s WHERE s.id = conversations.session_id)
            """)
        )

    await db.commit()
    logger.info(f"Deleted {total} orphaned records: {details}")

    return CleanupResponse(deleted_count=total, details=details)


@router.get("/health")
async def devops_health(
    _: Annotated[None, Depends(require_devops_secret)],
) -> dict[str, str]:
    """Simple health check for DevOps API authentication verification."""
    return {"status": "ok", "service": "devops-api"}
