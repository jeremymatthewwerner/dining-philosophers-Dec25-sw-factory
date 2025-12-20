"""Add spend_limit to users

Revision ID: c1a2b3d4e5f6
Revises: 815724a57297
Create Date: 2025-12-18

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1a2b3d4e5f6"
down_revision: str | Sequence[str] | None = "815724a57297"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add spend_limit column to users table."""
    op.add_column(
        "users",
        sa.Column("spend_limit", sa.Float, nullable=False, server_default="10.0"),
    )


def downgrade() -> None:
    """Remove spend_limit column from users table."""
    op.drop_column("users", "spend_limit")
