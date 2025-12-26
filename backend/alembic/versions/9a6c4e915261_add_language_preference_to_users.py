"""add_language_preference_to_users

Revision ID: 9a6c4e915261
Revises: c1a2b3d4e5f6
Create Date: 2025-12-26 19:12:49.878328

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9a6c4e915261"
down_revision: str | Sequence[str] | None = "c1a2b3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add language_preference column to users table."""
    op.add_column(
        "users",
        sa.Column("language_preference", sa.String(10), nullable=False, server_default="en"),
    )


def downgrade() -> None:
    """Remove language_preference column from users table."""
    op.drop_column("users", "language_preference")
