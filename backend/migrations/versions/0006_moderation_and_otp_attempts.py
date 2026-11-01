"""Add OTP attempt counting, media reports and user blocks

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "magic_link_tokens",
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
    )

    # Deleting an admin's account must not fail because they reviewed media.
    op.drop_constraint("media_submissions_reviewed_by_fkey", "media_submissions", type_="foreignkey")
    op.create_foreign_key(
        "media_submissions_reviewed_by_fkey",
        "media_submissions",
        "users",
        ["reviewed_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_media_submissions_park_status", "media_submissions", ["park_id", "status"])
    op.create_index("idx_media_submissions_user_status", "media_submissions", ["user_id", "status"])

    op.create_table(
        "media_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("media_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("media_submissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reporter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reason", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("media_id", "reporter_id", name="uq_media_report_reporter"),
    )

    op.create_table(
        "user_blocks",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("blocker_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("blocked_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("blocker_id", "blocked_id", name="uq_user_block"),
        sa.CheckConstraint("blocker_id <> blocked_id", name="ck_user_block_not_self"),
    )


def downgrade() -> None:
    op.drop_table("user_blocks")
    op.drop_table("media_reports")
    op.drop_index("idx_media_submissions_user_status", table_name="media_submissions")
    op.drop_index("idx_media_submissions_park_status", table_name="media_submissions")
    op.drop_constraint("media_submissions_reviewed_by_fkey", "media_submissions", type_="foreignkey")
    op.create_foreign_key(
        "media_submissions_reviewed_by_fkey", "media_submissions", "users", ["reviewed_by"], ["id"]
    )
    op.drop_column("magic_link_tokens", "attempts")
