"""Initial schema with PostGIS

Revision ID: 0001
Revises:
Create Date: 2026-03-20
"""
from typing import Sequence, Union

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "skateparks",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), unique=True, nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("address", sa.String(512)),
        sa.Column("city", sa.String(128)),
        sa.Column("state", sa.String(64)),
        sa.Column("country", sa.String(64), server_default="US"),
        sa.Column("zip_code", sa.String(16)),
        sa.Column("geom", geoalchemy2.Geometry("POINT", srid=4326), nullable=False),
        sa.Column("park_type", sa.String(32)),
        sa.Column("features", postgresql.JSONB()),
        sa.Column("rating", sa.Float()),
        sa.Column("difficulty", sa.String(32)),
        sa.Column("lighting", sa.Boolean()),
        sa.Column("is_free", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("hours", postgresql.JSONB()),
        sa.Column("surface", sa.String(64)),
        sa.Column("source", sa.String(64)),
        sa.Column("source_id", sa.String(128)),
        sa.Column("hero_image_url", sa.String(512)),
        sa.Column("verified", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("data_quality_score", sa.Float()),
        sa.Column("source_ids", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_skateparks_city_state", "skateparks", ["city", "state"])
    op.create_index(
        "idx_skateparks_source",
        "skateparks",
        ["source", "source_id"],
        unique=True,
        postgresql_where=sa.text("source IS NOT NULL AND source_id IS NOT NULL"),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("display_name", sa.String(128)),
        sa.Column("is_admin", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_login", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "magic_link_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, index=True),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "favorites",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("park_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("skateparks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "park_id", name="uq_user_park_favorite"),
    )

    op.create_table(
        "media_submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("park_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("skateparks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("media_type", sa.String(16), nullable=False),
        sa.Column("file_url", sa.String(512), nullable=False),
        sa.Column("thumbnail_url", sa.String(512)),
        sa.Column("description", sa.Text()),
        sa.Column("tags", postgresql.ARRAY(sa.String())),
        sa.Column("status", sa.String(16), server_default="pending"),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("media_submissions")
    op.drop_table("favorites")
    op.drop_table("magic_link_tokens")
    op.drop_table("users")
    op.drop_index("idx_skateparks_source", table_name="skateparks")
    op.drop_index("idx_skateparks_city_state", table_name="skateparks")
    op.drop_table("skateparks")
    op.execute("DROP EXTENSION IF EXISTS postgis")
