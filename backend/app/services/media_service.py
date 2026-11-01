import asyncio
import logging
import uuid
from datetime import datetime, timezone
from html import escape

import resend
from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.media import MediaSubmission
from app.models.moderation import MediaReport, UserBlock
from app.models.skatepark import Skatepark
from app.models.user import User
from app.utils.storage import InvalidUpload, store_media

logger = logging.getLogger(__name__)


async def submit_media(
    db: AsyncSession,
    park_id: uuid.UUID,
    user_id: uuid.UUID,
    file_bytes: bytes,
    description: str | None = None,
    tags: list[str] | None = None,
) -> dict | str:
    """Submit media. Returns dict on success, error string on failure."""
    park_result = await db.execute(
        select(Skatepark.id, Skatepark.name).where(Skatepark.id == park_id)
    )
    park = park_result.first()
    if not park:
        return "Park not found"

    try:
        stored = await store_media(file_bytes, str(park_id))
    except InvalidUpload as exc:
        return str(exc)

    submission = MediaSubmission(
        park_id=park_id,
        user_id=user_id,
        media_type=stored.media_type,
        file_url=stored.file_url,
        thumbnail_url=stored.thumbnail_url,
        description=description,
        tags=tags,
        status="pending",
    )
    db.add(submission)
    await db.flush()

    await _notify_admins(db, submission, park.name, user_id)

    return {
        "id": submission.id,
        "park_id": submission.park_id,
        "user_id": submission.user_id,
        "media_type": submission.media_type,
        "file_url": submission.file_url,
        "thumbnail_url": submission.thumbnail_url,
        "description": submission.description,
        "tags": submission.tags,
        "status": submission.status,
        "submitted_at": submission.submitted_at,
    }


async def _send_admin_email(subject: str, rows: dict[str, str]) -> None:
    if not settings.admin_email_list or not settings.RESEND_API_KEY:
        return

    table = "".join(
        f'<tr><td style="padding: 8px; font-weight: bold;">{escape(key)}:</td>'
        f'<td style="padding: 8px;">{escape(value)}</td></tr>'
        for key, value in rows.items()
    )
    try:
        resend.api_key = settings.RESEND_API_KEY
        await asyncio.to_thread(resend.Emails.send, {
            "from": settings.RESEND_FROM_EMAIL,
            "to": settings.admin_email_list,
            "subject": subject,
            "html": f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2>{escape(subject)}</h2>
                <table style="border-collapse: collapse; width: 100%;">{table}</table>
                <p style="margin-top: 20px;">Review it in the Shuvit app under Profile &gt; Review Queue.</p>
            </div>
            """,
        })
    except Exception:
        logger.exception("Failed to send admin notification")


async def _notify_admins(
    db: AsyncSession,
    submission: MediaSubmission,
    park_name: str,
    user_id: uuid.UUID,
) -> None:
    user_result = await db.execute(select(User.email).where(User.id == user_id))
    await _send_admin_email(
        f"New media submission for {park_name}",
        {
            "Park": park_name,
            "User": user_result.scalar_one_or_none() or "unknown",
            "Type": submission.media_type,
            "Description": submission.description or "None",
            "Tags": ", ".join(submission.tags) if submission.tags else "None",
        },
    )


async def get_approved_media(
    db: AsyncSession, park_id: uuid.UUID, viewer_id: uuid.UUID | None = None
) -> list[dict]:
    query = (
        select(MediaSubmission, User.display_name.label("contributor_name"))
        .join(User, MediaSubmission.user_id == User.id)
        .where(
            MediaSubmission.park_id == park_id,
            MediaSubmission.status == "approved",
        )
        .order_by(MediaSubmission.submitted_at.desc())
    )
    if viewer_id:
        blocked = select(UserBlock.blocked_id).where(UserBlock.blocker_id == viewer_id)
        query = query.where(MediaSubmission.user_id.not_in(blocked))

    rows = (await db.execute(query)).all()
    return [
        {
            "id": r.MediaSubmission.id,
            "park_id": r.MediaSubmission.park_id,
            "user_id": r.MediaSubmission.user_id,
            "media_type": r.MediaSubmission.media_type,
            "file_url": r.MediaSubmission.file_url,
            "thumbnail_url": r.MediaSubmission.thumbnail_url,
            "description": r.MediaSubmission.description,
            "tags": r.MediaSubmission.tags,
            "status": r.MediaSubmission.status,
            "submitted_at": r.MediaSubmission.submitted_at,
            "contributor_name": r.contributor_name,
        }
        for r in rows
    ]


async def get_review_queue(db: AsyncSession) -> list[dict]:
    """Pending submissions, plus approved media with unresolved reports."""
    open_reports = (
        select(func.count(MediaReport.id))
        .where(MediaReport.media_id == MediaSubmission.id, MediaReport.resolved_at.is_(None))
        .correlate(MediaSubmission)
        .scalar_subquery()
    )
    query = (
        select(
            MediaSubmission,
            Skatepark.name.label("park_name"),
            User.display_name.label("contributor_name"),
            open_reports.label("report_count"),
        )
        .join(Skatepark, MediaSubmission.park_id == Skatepark.id)
        .join(User, MediaSubmission.user_id == User.id)
        .where(or_(MediaSubmission.status == "pending", open_reports > 0))
        .order_by(open_reports.desc(), MediaSubmission.submitted_at)
    )
    rows = (await db.execute(query)).all()
    return [
        {
            "id": r.MediaSubmission.id,
            "park_id": r.MediaSubmission.park_id,
            "park_name": r.park_name,
            "user_id": r.MediaSubmission.user_id,
            "contributor_name": r.contributor_name,
            "media_type": r.MediaSubmission.media_type,
            "file_url": r.MediaSubmission.file_url,
            "thumbnail_url": r.MediaSubmission.thumbnail_url,
            "description": r.MediaSubmission.description,
            "status": r.MediaSubmission.status,
            "report_count": r.report_count,
            "submitted_at": r.MediaSubmission.submitted_at,
        }
        for r in rows
    ]


async def approve_media(
    db: AsyncSession,
    media_id: uuid.UUID,
    admin_id: uuid.UUID,
    action: str,
) -> dict | None:
    result = await db.execute(
        select(MediaSubmission).where(MediaSubmission.id == media_id)
    )
    submission = result.scalar_one_or_none()
    if not submission:
        return None

    now = datetime.now(timezone.utc)
    submission.status = "approved" if action == "approve" else "rejected"
    submission.reviewed_by = admin_id
    submission.reviewed_at = now
    await db.execute(
        update(MediaReport)
        .where(MediaReport.media_id == media_id, MediaReport.resolved_at.is_(None))
        .values(resolved_at=now)
    )
    await db.flush()

    return {
        "id": submission.id,
        "status": submission.status,
        "reviewed_at": submission.reviewed_at,
    }


async def report_media(
    db: AsyncSession, media_id: uuid.UUID, reporter_id: uuid.UUID, reason: str | None
) -> bool:
    """Record a report. Returns False if the media doesn't exist."""
    result = await db.execute(
        select(MediaSubmission, Skatepark.name)
        .join(Skatepark, MediaSubmission.park_id == Skatepark.id)
        .where(MediaSubmission.id == media_id)
    )
    row = result.first()
    if not row:
        return False

    inserted = await db.execute(
        insert(MediaReport)
        .values(id=uuid.uuid4(), media_id=media_id, reporter_id=reporter_id, reason=reason)
        .on_conflict_do_nothing(constraint="uq_media_report_reporter")
        .returning(MediaReport.id)
    )
    if inserted.scalar_one_or_none():
        await _send_admin_email(
            f"Media reported at {row[1]}",
            {"Park": row[1], "Media": str(media_id), "Reason": reason or "None given"},
        )
    return True
