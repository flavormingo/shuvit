"""Add otp_hash to magic_link_tokens

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("magic_link_tokens", sa.Column("otp_hash", sa.String(128)))


def downgrade() -> None:
    op.drop_column("magic_link_tokens", "otp_hash")
