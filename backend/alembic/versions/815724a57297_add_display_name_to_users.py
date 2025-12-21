"""add_display_name_to_users

Revision ID: 815724a57297
Revises: 18932bd079f0
Create Date: 2025-12-17 16:51:03.779056

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "815724a57297"
down_revision: str | Sequence[str] | None = "18932bd079f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add display_name column to users table."""
    op.add_column("users", sa.Column("display_name", sa.String(100), nullable=True))


def downgrade() -> None:
    """Remove display_name column from users table."""
    op.drop_column("users", "display_name")
