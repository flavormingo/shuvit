import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_user, get_current_user
from app.database import get_db
from app.models.user import User
from app.redis import get_redis
from app.schemas.media import MediaApproveAction, MediaSubmissionOut
from app.services import media_service

MEDIA_RATE_LIMIT = 10  # max submissions per hour

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
    tags: str | None = Form(None),  # comma-separated
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Rate limit
    r = await get_redis()
    if r:
        rate_key = f"media_rate:{user.id}"
        count = await r.incr(rate_key)
        if count == 1:
            await r.expire(rate_key, 3600)
        if count > MEDIA_RATE_LIMIT:
            raise HTTPException(status_code=429, detail="Too many submissions. Try again later.")

    file_bytes = await file.read()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None

    result = await media_service.submit_media(
        db=db,
        park_id=park_id,
        user_id=user.id,
        file_bytes=file_bytes,
        content_type=file.content_type or "application/octet-stream",
        description=description,
        tags=tag_list,
    )

    if isinstance(result, str):
        raise HTTPException(status_code=400, detail=result)

    return result


@router.get("/parks/{park_id}/media", response_model=list[MediaSubmissionOut])
async def list_media(
    park_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    return await media_service.get_approved_media(db, park_id)


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
