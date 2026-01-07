"""Add feedbacks table and screenshot columns

Revision ID: f8a9b0c1d2e3
Revises: d2b3c4e5f6g7
Create Date: 2026-01-07

This migration ensures the feedbacks table exists with all required columns,
including the screenshot_data and screenshot_filename columns that were added
after the initial feedback feature.

For production databases where the feedbacks table exists but is missing
the screenshot columns, this adds them. For new databases, it creates the
full table.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f8a9b0c1d2e3"
down_revision: str | Sequence[str] | None = "d2b3c4e5f6g7"
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
    """Create feedbacks table if missing, or add screenshot columns if needed."""
    if not table_exists("feedbacks"):
        # Create the full feedbacks table
        op.create_table(
            "feedbacks",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "feedback_type",
                sa.Enum("bug", "feature", "other", name="feedbacktype"),
                nullable=False,
                server_default="bug",
            ),
            sa.Column("message", sa.Text, nullable=False),
            sa.Column("email", sa.String(255), nullable=True),
            sa.Column("name", sa.String(100), nullable=True),
            sa.Column("user_agent", sa.Text, nullable=True),
            sa.Column("screenshot_data", sa.Text, nullable=True),
            sa.Column("screenshot_filename", sa.String(255), nullable=True),
            sa.Column(
                "status",
                sa.Enum("new", "reviewed", "resolved", name="feedbackstatus"),
                nullable=False,
                server_default="new",
            ),
            sa.Column("github_issue_url", sa.String(500), nullable=True),
            sa.Column("ip_hash", sa.String(64), nullable=True),
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
    else:
        # Table exists - check if screenshot columns need to be added
        if not column_exists("feedbacks", "screenshot_data"):
            op.add_column(
                "feedbacks",
                sa.Column("screenshot_data", sa.Text, nullable=True),
            )

        if not column_exists("feedbacks", "screenshot_filename"):
            op.add_column(
                "feedbacks",
                sa.Column("screenshot_filename", sa.String(255), nullable=True),
            )


def downgrade() -> None:
    """Remove screenshot columns or drop feedbacks table."""
    if table_exists("feedbacks"):
        # Only drop the columns we added, keep the table
        if column_exists("feedbacks", "screenshot_filename"):
            op.drop_column("feedbacks", "screenshot_filename")
        if column_exists("feedbacks", "screenshot_data"):
            op.drop_column("feedbacks", "screenshot_data")
