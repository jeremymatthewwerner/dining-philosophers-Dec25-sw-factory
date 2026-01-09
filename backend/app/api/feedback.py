"""Feedback API endpoints."""

import hashlib
import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models import Feedback
from app.models.feedback import FeedbackStatus
from app.models.feedback import FeedbackType as FeedbackTypeModel
from app.schemas.feedback import (
    FeedbackCreate,
    FeedbackDetail,
    FeedbackResponse,
    MarkProcessedRequest,
    MarkProcessedResponse,
    PendingFeedbackResponse,
)

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
        username=data.username,
        user_agent=data.user_agent,
        screenshot_data=data.screenshot_data,
        screenshot_filename=data.screenshot_filename,
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


def verify_feedback_processor_secret(secret: str) -> None:
    """Verify the feedback processor secret.

    Raises HTTPException 403 if secret is invalid.
    """
    settings = get_settings()
    expected_secret = settings.feedback_processor_secret

    if not expected_secret:
        logger.warning("FEEDBACK_PROCESSOR_SECRET not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Feedback processing not configured",
        )

    if secret != expected_secret:
        logger.warning("Invalid feedback processor secret provided")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid secret",
        )


@router.get("/pending", response_model=PendingFeedbackResponse)
async def get_pending_feedback(
    secret: str = Query(..., description="Feedback processor secret"),
    limit: int = Query(default=10, ge=1, le=50, description="Maximum number of items"),
    db: AsyncSession = Depends(get_db),
) -> PendingFeedbackResponse:
    """Get pending feedback items for processing.

    This endpoint is protected by a secret and used by the DevOps workflow
    to fetch pending feedback and convert them to GitHub issues.
    """
    verify_feedback_processor_secret(secret)

    # Fetch pending feedback (status = NEW)
    result = await db.execute(
        select(Feedback)
        .where(Feedback.status == FeedbackStatus.NEW)
        .order_by(Feedback.created_at.asc())
        .limit(limit)
    )
    feedbacks = result.scalars().all()

    feedback_details = [
        FeedbackDetail(
            id=fb.id,
            feedback_type=fb.feedback_type.value
            if hasattr(fb.feedback_type, "value")
            else fb.feedback_type,
            message=fb.message,
            email=fb.email,
            name=fb.name,
            username=fb.username,
            user_agent=fb.user_agent,
            status=fb.status.value if hasattr(fb.status, "value") else fb.status,
            github_issue_url=fb.github_issue_url,
            created_at=fb.created_at,
            updated_at=fb.updated_at,
        )
        for fb in feedbacks
    ]

    logger.info(f"Returning {len(feedback_details)} pending feedback items")
    return PendingFeedbackResponse(count=len(feedback_details), feedbacks=feedback_details)


@router.patch("/{feedback_id}/processed", response_model=MarkProcessedResponse)
async def mark_feedback_processed(
    feedback_id: str,
    data: MarkProcessedRequest,
    secret: str = Query(..., description="Feedback processor secret"),
    db: AsyncSession = Depends(get_db),
) -> MarkProcessedResponse:
    """Mark feedback as processed with a GitHub issue URL.

    This endpoint is protected by a secret and used by the DevOps workflow
    after creating a GitHub issue from the feedback.
    """
    verify_feedback_processor_secret(secret)

    # Find the feedback
    result = await db.execute(select(Feedback).where(Feedback.id == feedback_id))
    feedback = result.scalar_one_or_none()

    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feedback {feedback_id} not found",
        )

    # Update the feedback
    feedback.status = FeedbackStatus.REVIEWED
    feedback.github_issue_url = data.github_issue_url
    await db.commit()

    logger.info(f"Feedback {feedback_id} marked as processed with issue: {data.github_issue_url}")

    return MarkProcessedResponse(
        success=True,
        feedback_id=feedback_id,
        github_issue_url=data.github_issue_url,
    )
