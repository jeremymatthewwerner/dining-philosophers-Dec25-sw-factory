"""ThinkerKnowledge model for caching research about thinkers."""

from enum import Enum
from typing import Any

from sqlalchemy import JSON, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, generate_uuid


class ResearchStatus(str, Enum):
    """Status of knowledge research for a thinker."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    FAILED = "failed"


class ThinkerKnowledge(Base, TimestampMixin):
    """Cached knowledge and research about a thinker.

    This model stores research results that persist across app reboots
    and are shared across all users and conversations. When a thinker
    is selected, background research is triggered to gather content
    from various sources (Wikipedia, public domain texts, etc.).

    The research_data field uses JSONB for flexible storage of:
    - Wikipedia summaries and key facts
    - Public domain text excerpts
    - Key quotes and writings
    - Analysis and digests
    - Source metadata
    """

    __tablename__ = "thinker_knowledge"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    # Canonical name of the thinker (e.g., "Socrates", "Albert Einstein")
    # This is the unique key for lookup - same thinker shares knowledge across users
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    # Current status of the research process
    status: Mapped[ResearchStatus] = mapped_column(
        SQLEnum(ResearchStatus),
        nullable=False,
        default=ResearchStatus.PENDING,
        index=True,
    )
    # Flexible JSONB storage for all research data
    # Structure:
    # {
    #   "wikipedia": {
    #     "summary": "...",
    #     "key_facts": [...],
    #     "birth_death": "...",
    #     "notable_works": [...],
    #   },
    #   "quotes": [...],
    #   "writings": [...],
    #   "analysis": "...",
    #   "sources": [{"type": "...", "url": "...", "fetched_at": "..."}],
    # }
    research_data: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    # Error message if research failed
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
