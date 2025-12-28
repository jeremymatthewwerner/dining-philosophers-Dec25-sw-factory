"""Add thinker_knowledge table for cached research

Revision ID: d2b3c4e5f6g7
Revises: 9a6c4e915261
Create Date: 2025-12-28

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d2b3c4e5f6g7"
down_revision: str | Sequence[str] | None = "9a6c4e915261"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create thinker_knowledge table for caching research about thinkers."""
    op.create_table(
        "thinker_knowledge",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column(
            "status",
            sa.Enum("pending", "in_progress", "complete", "failed", name="researchstatus"),
            nullable=False,
            server_default="pending",
            index=True,
        ),
        sa.Column("research_data", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )


def downgrade() -> None:
    """Drop thinker_knowledge table."""
    op.drop_table("thinker_knowledge")
    # Drop the enum type
    op.execute("DROP TYPE IF EXISTS researchstatus")
