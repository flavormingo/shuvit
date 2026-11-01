import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.media import MediaSubmission
from app.models.skatepark import Skatepark
from app.models.user import User
from app.schemas.media import MediaSubmissionOut
from app.schemas.user import UserOut, UserProfile, UserUpdate
from app.utils.storage import save_upload, validate_upload

router = APIRouter(prefix="/user", tags=["user"])


def _get_rank(count: int) -> str:
    if count >= 100:
        return "Legend"
    if count >= 50:
        return "Wizard"
    if count >= 10:
        return "Pro"
    return "Rookie"


@router.get("/me", response_model=UserOut)
async def get_me(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserOut)
async def update_me(
    body: UserUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.display_name is not None:
        import re
        name = body.display_name.strip()
        if not name or len(name) > 20 or not re.match(r'^[a-zA-Z0-9]+$', name):
            raise HTTPException(status_code=400, detail="Name must be 1-20 characters, letters and numbers only")
        body.display_name = name
        # Check uniqueness (case-insensitive)
        existing = await db.execute(
            select(User.id).where(
                func.lower(User.display_name) == body.display_name.lower(),
                User.id != user.id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Name is already taken")
        user.display_name = body.display_name
    await db.flush()
    return user


@router.post("/me/avatar", response_model=UserOut)
async def upload_avatar(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    file_bytes = await file.read()
    content_type = file.content_type or "application/octet-stream"

    error = validate_upload(content_type, len(file_bytes))
    if error:
        raise HTTPException(status_code=400, detail=error)

    file_url, _ = await save_upload(file_bytes, content_type, "avatars")
    user.avatar_url = file_url
    await db.flush()
    return user


@router.get("/me/contributions")
async def my_contributions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(
            MediaSubmission,
            Skatepark.name.label("park_name"),
            Skatepark.id.label("park_id"),
        )
        .join(Skatepark, MediaSubmission.park_id == Skatepark.id)
        .where(
            MediaSubmission.user_id == user.id,
            MediaSubmission.status == "approved",
        )
        .order_by(MediaSubmission.submitted_at.desc())
    )
    rows = (await db.execute(query)).all()

    return [
        {
            "id": r.MediaSubmission.id,
            "park_id": r.park_id,
            "park_name": r.park_name,
            "media_type": r.MediaSubmission.media_type,
            "file_url": r.MediaSubmission.file_url,
            "thumbnail_url": r.MediaSubmission.thumbnail_url,
            "description": r.MediaSubmission.description,
            "submitted_at": r.MediaSubmission.submitted_at,
        }
        for r in rows
    ]


@router.get("/me/stats")
async def my_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    count = (
        await db.execute(
            select(func.count(MediaSubmission.id)).where(
                MediaSubmission.user_id == user.id,
                MediaSubmission.status == "approved",
            )
        )
    ).scalar() or 0

    rank = _get_rank(count)

    # Progress to next rank
    thresholds = {"Rookie": 10, "Pro": 50, "Wizard": 100, "Legend": None}
    next_threshold = thresholds[rank]
    if next_threshold:
        if rank == "Rookie":
            progress = count / 10
        elif rank == "Pro":
            progress = (count - 10) / 40
        else:
            progress = (count - 50) / 50
    else:
        progress = 1.0

    next_rank = {"Rookie": "Pro", "Pro": "Wizard", "Wizard": "Legend", "Legend": None}

    return {
        "approved_count": count,
        "rank": rank,
        "next_rank": next_rank[rank],
        "progress": round(min(progress, 1.0), 2),
        "next_threshold": next_threshold,
    }


@router.get("/{user_id}/profile", response_model=UserProfile)
async def get_user_profile(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    count = (
        await db.execute(
            select(func.count(MediaSubmission.id)).where(
                MediaSubmission.user_id == user_id,
                MediaSubmission.status == "approved",
            )
        )
    ).scalar() or 0

    parks_count = (
        await db.execute(
            select(func.count(func.distinct(MediaSubmission.park_id))).where(
                MediaSubmission.user_id == user_id,
                MediaSubmission.status == "approved",
            )
        )
    ).scalar() or 0

    return UserProfile(
        id=user.id,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        approved_count=count,
        parks_count=parks_count,
        rank=_get_rank(count),
    )


@router.get("/{user_id}/contributions")
async def user_contributions(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(
            MediaSubmission,
            Skatepark.name.label("park_name"),
        )
        .join(Skatepark, MediaSubmission.park_id == Skatepark.id)
        .where(
            MediaSubmission.user_id == user_id,
            MediaSubmission.status == "approved",
        )
        .order_by(MediaSubmission.submitted_at.desc())
    )
    rows = (await db.execute(query)).all()

    return [
        {
            "id": r.MediaSubmission.id,
            "park_id": r.MediaSubmission.park_id,
            "park_name": r.park_name,
            "media_type": r.MediaSubmission.media_type,
            "file_url": r.MediaSubmission.file_url,
            "thumbnail_url": r.MediaSubmission.thumbnail_url,
            "description": r.MediaSubmission.description,
            "submitted_at": r.MediaSubmission.submitted_at,
        }
        for r in rows
    ]
