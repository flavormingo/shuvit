"""Add avatar_url to users

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_url", sa.String(512)))


def downgrade() -> None:
    op.drop_column("users", "avatar_url")
