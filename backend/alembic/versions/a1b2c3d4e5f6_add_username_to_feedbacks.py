"""Add username column to feedbacks table

Revision ID: a1b2c3d4e5f6
Revises: f8a9b0c1d2e3
Create Date: 2026-01-09

This migration adds a username column to the feedbacks table to store
the Dining Philosophers username of logged-in users who submit feedback.
This helps with debugging and context when users report issues.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "f8a9b0c1d2e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    conn = op.get_bind()
    inspector = inspect(conn)
    return table_name in inspector.get_table_names()


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    """Add username column to feedbacks table if it doesn't exist."""
    if table_exists("feedbacks") and not column_exists("feedbacks", "username"):
        op.add_column(
            "feedbacks",
            sa.Column("username", sa.String(50), nullable=True),
        )


def downgrade() -> None:
    """Remove username column from feedbacks table."""
    if table_exists("feedbacks") and column_exists("feedbacks", "username"):
        op.drop_column("feedbacks", "username")
