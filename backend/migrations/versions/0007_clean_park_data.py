"""Remove skate shops and placeholder classifications from skateparks

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-01
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DELETE FROM skateparks
        WHERE source_id IN ('osm-node-11057815269', 'osm-node-11178928523', 'osm-node-11178968714')
          AND NOT EXISTS (SELECT 1 FROM favorites WHERE favorites.park_id = skateparks.id)
          AND NOT EXISTS (SELECT 1 FROM media_submissions WHERE media_submissions.park_id = skateparks.id)
    """)
    op.execute("UPDATE skateparks SET park_type = NULL WHERE source = 'osm' AND park_type = 'mixed'")
    op.execute("UPDATE skateparks SET features = NULL WHERE features ? 'indoor_outdoor' AND features - 'indoor_outdoor' = '{}'::jsonb")


def downgrade() -> None:
    pass
