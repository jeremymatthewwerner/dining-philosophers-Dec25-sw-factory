"""Feedback API endpoints."""

import hashlib
import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import Feedback
from app.models.feedback import FeedbackStatus
from app.models.feedback import FeedbackType as FeedbackTypeModel
from app.schemas.feedback import FeedbackCreate, FeedbackResponse

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
