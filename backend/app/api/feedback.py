"""Feedback API endpoints."""

import hashlib
import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models import Feedback
from app.models.feedback import FeedbackStatus
from app.models.feedback import FeedbackType as FeedbackTypeModel
from app.schemas.feedback import FeedbackCreate, FeedbackDetail, FeedbackResponse

router = APIRouter()
logger = logging.getLogger(__name__)

# Rate limiting constants
MAX_SUBMISSIONS_PER_HOUR = 5


def hash_ip(ip: str) -> str:
    """Hash IP address for privacy-preserving rate limiting."""
    return hashlib.sha256(ip.encode()).hexdigest()


def get_client_ip(request: Request) -> str:
    """Get client IP address from request headers.

    Checks X-Forwarded-For header first (for proxied requests),
    then falls back to direct client IP.
    """
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        # Get the first IP in the chain (original client)
        return x_forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    data: FeedbackCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> FeedbackResponse:
    """Submit user feedback.

    This endpoint allows users to submit bug reports and feature requests
    without requiring a GitHub account. No authentication required.

    Rate limiting: Maximum 5 submissions per hour per IP address.
    """
    # Get and hash client IP for rate limiting
    client_ip = get_client_ip(request)
    ip_hash = hash_ip(client_ip)

    # Check rate limit
    one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
    result = await db.execute(
        select(func.count(Feedback.id)).where(
            Feedback.ip_hash == ip_hash,
            Feedback.created_at >= one_hour_ago,
        )
    )
    submission_count = result.scalar() or 0

    if submission_count >= MAX_SUBMISSIONS_PER_HOUR:
        logger.warning(f"Rate limit exceeded for IP hash: {ip_hash[:8]}...")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many feedback submissions. Please try again later.",
        )

    # Map schema enum to model enum
    feedback_type_map = {
        "bug": FeedbackTypeModel.BUG,
        "feature": FeedbackTypeModel.FEATURE,
        "other": FeedbackTypeModel.OTHER,
    }
    model_feedback_type = feedback_type_map.get(data.feedback_type.value, FeedbackTypeModel.OTHER)

    # Create feedback record
    feedback = Feedback(
        feedback_type=model_feedback_type,
        message=data.message,
        email=data.email,
        name=data.name,
        user_agent=data.user_agent,
        status=FeedbackStatus.NEW,
        ip_hash=ip_hash,
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)

    logger.info(f"New feedback submitted: {feedback.id} (type: {data.feedback_type})")

    return FeedbackResponse(
        id=feedback.id,
        message="Thank you for your feedback! We appreciate you taking the time to help us improve.",
    )


class PendingFeedbackResponse(BaseModel):
    """Response schema for pending feedback list."""

    feedbacks: list[FeedbackDetail]
    count: int


@router.get("/pending", response_model=PendingFeedbackResponse)
async def get_pending_feedback(
    secret: str = Query(..., description="Feedback processor secret for authentication"),
    limit: int = Query(default=10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> PendingFeedbackResponse:
    """Get pending feedback items waiting to be converted to GitHub issues.

    **SECURITY**: This endpoint is protected by FEEDBACK_PROCESSOR_SECRET and is
    used by the DevOps workflow to fetch feedback that needs to be converted to
    GitHub issues.

    **Purpose**: Part of the feedback-to-GitHub-issue pipeline. The DevOps agent
    polls this endpoint to find new feedback, creates GitHub issues, then calls
    the mark-processed endpoint.

    Args:
        secret: The feedback processor secret for authentication
        limit: Maximum number of items to return (default 10, max 100)

    Returns:
        List of pending feedback items
    """
    settings = get_settings()

    # Verify secret is configured
    if not settings.feedback_processor_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Feedback processor secret not configured",
        )

    # Verify provided secret matches
    if secret != settings.feedback_processor_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid feedback processor secret",
        )

    # Query for pending feedback
    result = await db.execute(
        select(Feedback)
        .where(Feedback.status == FeedbackStatus.NEW)
        .order_by(Feedback.created_at.asc())
        .limit(limit)
    )
    feedbacks = result.scalars().all()

    return PendingFeedbackResponse(
        feedbacks=[
            FeedbackDetail(
                id=f.id,
                feedback_type=f.feedback_type.value
                if hasattr(f.feedback_type, "value")
                else str(f.feedback_type),
                message=f.message,
                email=f.email,
                name=f.name,
                user_agent=f.user_agent,
                status=f.status.value if hasattr(f.status, "value") else str(f.status),
                github_issue_url=f.github_issue_url,
                created_at=f.created_at,
                updated_at=f.updated_at,
            )
            for f in feedbacks
        ],
        count=len(feedbacks),
    )


class MarkProcessedRequest(BaseModel):
    """Request schema for marking feedback as processed."""

    github_issue_url: str


class MarkProcessedResponse(BaseModel):
    """Response schema for marking feedback as processed."""

    id: str
    status: str
    github_issue_url: str
    message: str


@router.patch("/{feedback_id}/processed", response_model=MarkProcessedResponse)
async def mark_feedback_processed(
    feedback_id: str,
    request: MarkProcessedRequest,
    secret: str = Query(..., description="Feedback processor secret for authentication"),
    db: AsyncSession = Depends(get_db),
) -> MarkProcessedResponse:
    """Mark a feedback item as processed after creating a GitHub issue.

    **SECURITY**: This endpoint is protected by FEEDBACK_PROCESSOR_SECRET.

    **Purpose**: After the DevOps agent creates a GitHub issue from feedback,
    it calls this endpoint to mark the feedback as processed and store the
    issue URL.

    Args:
        feedback_id: The ID of the feedback to mark as processed
        request: Contains the GitHub issue URL
        secret: The feedback processor secret for authentication

    Returns:
        Updated feedback status
    """
    settings = get_settings()

    # Verify secret is configured
    if not settings.feedback_processor_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Feedback processor secret not configured",
        )

    # Verify provided secret matches
    if secret != settings.feedback_processor_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid feedback processor secret",
        )

    # Find the feedback
    result = await db.execute(select(Feedback).where(Feedback.id == feedback_id))
    feedback = result.scalar_one_or_none()

    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feedback not found",
        )

    # Update the feedback
    feedback.status = FeedbackStatus.REVIEWED
    feedback.github_issue_url = request.github_issue_url
    await db.commit()
    await db.refresh(feedback)

    logger.info(
        f"Feedback {feedback_id} marked as processed with issue: {request.github_issue_url}"
    )

    return MarkProcessedResponse(
        id=feedback.id,
        status=feedback.status.value if hasattr(feedback.status, "value") else str(feedback.status),
        github_issue_url=feedback.github_issue_url or "",
        message="Feedback marked as processed and linked to GitHub issue",
    )
