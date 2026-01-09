"""Feedback model for storing user feedback submitted via the app."""

from enum import Enum as PyEnum

from sqlalchemy import Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, generate_uuid


class FeedbackType(str, PyEnum):
    """Type of feedback submitted."""

    BUG = "bug"
    FEATURE = "feature"
    OTHER = "other"


class FeedbackStatus(str, PyEnum):
    """Status of feedback item."""

    NEW = "new"
    REVIEWED = "reviewed"
    RESOLVED = "resolved"


class Feedback(Base, TimestampMixin):
    """User feedback submitted through the in-app form.

    Allows users without GitHub accounts to submit bug reports and feature requests.
    Admins can review and optionally convert to GitHub issues.
    """

    __tablename__ = "feedbacks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)

    # Feedback content
    # Note: values_callable ensures SQLAlchemy uses enum values (lowercase)
    # instead of enum names (uppercase) when storing to PostgreSQL
    feedback_type: Mapped[str] = mapped_column(
        Enum(
            FeedbackType,
            values_callable=lambda x: [e.value for e in x],
            name="feedbacktype",
        ),
        default=FeedbackType.BUG,
        nullable=False,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Optional user info (for users who want to be contacted)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Dining Philosophers username (if logged in when submitting)
    username: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Browser/device info for debugging
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Screenshot attachment (base64 encoded)
    screenshot_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    screenshot_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Status tracking
    status: Mapped[str] = mapped_column(
        Enum(
            FeedbackStatus,
            values_callable=lambda x: [e.value for e in x],
            name="feedbackstatus",
        ),
        default=FeedbackStatus.NEW,
        nullable=False,
    )

    # Link to GitHub issue if created
    github_issue_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # IP address for rate limiting (hashed for privacy)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
