import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_user, get_current_user, get_current_user_optional
from app.database import get_db
from app.models.user import User
from app.redis import is_rate_limited
from app.schemas.media import (
    MediaApproveAction,
    MediaReportCreate,
    MediaSubmissionOut,
    ReviewQueueItem,
)
from app.services import media_service

MEDIA_SUBMISSIONS_PER_HOUR = 10

router = APIRouter(tags=["media"])


@router.post(
    "/parks/{park_id}/media",
    response_model=MediaSubmissionOut,
    status_code=201,
)
async def submit_media(
    park_id: uuid.UUID,
    file: UploadFile = File(...),
    description: str | None = Form(None),
    tags: str | None = Form(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if await is_rate_limited(f"media_rate:{user.id}", MEDIA_SUBMISSIONS_PER_HOUR, 3600):
        raise HTTPException(status_code=429, detail="Too many submissions. Try again later.")

    file_bytes = await file.read()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None

    result = await media_service.submit_media(
        db=db,
        park_id=park_id,
        user_id=user.id,
        file_bytes=file_bytes,
        description=description,
        tags=tag_list,
    )

    if isinstance(result, str):
        raise HTTPException(status_code=400, detail=result)

    return result


@router.get("/parks/{park_id}/media", response_model=list[MediaSubmissionOut])
async def list_media(
    park_id: uuid.UUID,
    viewer: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    return await media_service.get_approved_media(db, park_id, viewer.id if viewer else None)


@router.get("/media/review-queue", response_model=list[ReviewQueueItem])
async def review_queue(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    return await media_service.get_review_queue(db)


@router.post("/media/{media_id}/approve")
async def approve_media(
    media_id: uuid.UUID,
    body: MediaApproveAction,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await media_service.approve_media(db, media_id, admin.id, body.action)
    if not result:
        raise HTTPException(status_code=404, detail="Submission not found")
    return result


@router.post("/media/{media_id}/report", status_code=204)
async def report_media(
    media_id: uuid.UUID,
    body: MediaReportCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not await media_service.report_media(db, media_id, user.id, body.reason):
        raise HTTPException(status_code=404, detail="Media not found")
