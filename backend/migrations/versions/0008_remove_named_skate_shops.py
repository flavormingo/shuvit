"""Remove skate shops that are only identifiable by name

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-01
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DELETE FROM skateparks
        WHERE source = 'osm'
          AND name ~* '(skate|board)\\s*shop\\y'
          AND NOT EXISTS (SELECT 1 FROM favorites WHERE favorites.park_id = skateparks.id)
          AND NOT EXISTS (SELECT 1 FROM media_submissions WHERE media_submissions.park_id = skateparks.id)
    """)


def downgrade() -> None:
    pass
