"""Add unique constraint on display_name

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "idx_users_display_name_unique",
        "users",
        [sa.text("lower(display_name)")],
        unique=True,
        postgresql_where=sa.text("display_name IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_users_display_name_unique", table_name="users")
