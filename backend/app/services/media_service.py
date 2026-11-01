import asyncio
import logging
import uuid
from datetime import datetime, timezone
from html import escape

import resend
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.media import MediaSubmission
from app.models.skatepark import Skatepark
from app.models.user import User
from app.utils.storage import save_upload, validate_upload

logger = logging.getLogger(__name__)


async def submit_media(
    db: AsyncSession,
    park_id: uuid.UUID,
    user_id: uuid.UUID,
    file_bytes: bytes,
    content_type: str,
    description: str | None = None,
    tags: list[str] | None = None,
) -> dict | str:
    """Submit media. Returns dict on success, error string on failure."""
    error = validate_upload(content_type, len(file_bytes), file_bytes)
    if error:
        return error

    # Check park exists
    park_result = await db.execute(
        select(Skatepark.id, Skatepark.name).where(Skatepark.id == park_id)
    )
    park = park_result.first()
    if not park:
        return "Park not found"

    media_type = "image" if content_type.startswith("image/") else "video"
    file_url, thumbnail_url = await save_upload(file_bytes, content_type, str(park_id))

    submission = MediaSubmission(
        park_id=park_id,
        user_id=user_id,
        media_type=media_type,
        file_url=file_url,
        thumbnail_url=thumbnail_url,
        description=description,
        tags=tags,
        status="pending",
    )
    db.add(submission)
    await db.flush()

    # Notify admins
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


async def _notify_admins(
    db: AsyncSession,
    submission: MediaSubmission,
    park_name: str,
    user_id: uuid.UUID,
):
    """Send email notification to admins about new media submission."""
    if not settings.admin_email_list or not settings.RESEND_API_KEY:
        return

    user_result = await db.execute(select(User.email).where(User.id == user_id))
    user_email = user_result.scalar_one_or_none() or "unknown"

    try:
        resend.api_key = settings.RESEND_API_KEY
        await asyncio.to_thread(resend.Emails.send, {
                "from": settings.RESEND_FROM_EMAIL,
                "to": settings.admin_email_list,
                "subject": f"New media submission for {park_name}",
                "html": f"""
                <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2>New Media Submission</h2>
                    <table style="border-collapse: collapse; width: 100%;">
                        <tr><td style="padding: 8px; font-weight: bold;">Park:</td><td style="padding: 8px;">{escape(park_name)}</td></tr>
                        <tr><td style="padding: 8px; font-weight: bold;">User:</td><td style="padding: 8px;">{escape(user_email)}</td></tr>
                        <tr><td style="padding: 8px; font-weight: bold;">Type:</td><td style="padding: 8px;">{escape(submission.media_type)}</td></tr>
                        <tr><td style="padding: 8px; font-weight: bold;">Description:</td><td style="padding: 8px;">{escape(submission.description or 'None')}</td></tr>
                        <tr><td style="padding: 8px; font-weight: bold;">Tags:</td><td style="padding: 8px;">{escape(', '.join(submission.tags) if submission.tags else 'None')}</td></tr>
                    </table>
                    <p style="margin-top: 20px;">
                        <a href="{settings.BASE_URL}/api/v1/media/{submission.id}/approve" style="display: inline-block; background: #22c55e; color: #fff; padding: 10px 20px; border-radius: 6px; text-decoration: none; margin-right: 8px;">Review</a>
                    </p>
                </div>
                """,
            })
    except Exception:
        logger.exception("Failed to send admin notification")


async def get_approved_media(db: AsyncSession, park_id: uuid.UUID) -> list[dict]:
    query = (
        select(MediaSubmission, User.display_name.label("contributor_name"))
        .join(User, MediaSubmission.user_id == User.id)
        .where(
            MediaSubmission.park_id == park_id,
            MediaSubmission.status == "approved",
        )
        .order_by(MediaSubmission.submitted_at.desc())
    )
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

    if action not in ("approve", "reject"):
        return None

    submission.status = "approved" if action == "approve" else "rejected"
    submission.reviewed_by = admin_id
    submission.reviewed_at = datetime.now(timezone.utc)
    await db.flush()

    return {
        "id": submission.id,
        "status": submission.status,
        "reviewed_at": submission.reviewed_at,
    }
