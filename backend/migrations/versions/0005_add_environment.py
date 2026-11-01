"""Add environment column to skateparks (indoor/outdoor/both)

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "skateparks",
        sa.Column("environment", sa.String(16), nullable=True),
    )
    op.create_index(
        "idx_skateparks_environment",
        "skateparks",
        ["environment"],
    )
    # Backfill from features JSONB where scraper already classified indoor/outdoor
    op.execute("""
        UPDATE skateparks
        SET environment = CASE
            WHEN features->>'indoor_outdoor' = 'indoor/outdoor' THEN 'both'
            WHEN features->>'indoor_outdoor' IS NOT NULL THEN features->>'indoor_outdoor'
            ELSE 'outdoor'
        END
        WHERE environment IS NULL
    """)


def downgrade() -> None:
    op.drop_index("idx_skateparks_environment", table_name="skateparks")
    op.drop_column("skateparks", "environment")
