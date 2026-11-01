import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.media import MediaSubmission
from app.models.moderation import UserBlock
from app.models.skatepark import Skatepark
from app.models.user import MagicLinkToken, User
from app.schemas.user import UserOut, UserProfile, UserUpdate
from app.utils.storage import InvalidUpload, delete_media_file, store_avatar

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
    try:
        file_url = await store_avatar(await file.read())
    except InvalidUpload as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    previous = user.avatar_url
    user.avatar_url = file_url
    await db.commit()
    delete_media_file(previous)
    return user


@router.delete("/me", status_code=204)
async def delete_me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete the account, its contributions and their files."""
    rows = await db.execute(
        select(MediaSubmission.file_url, MediaSubmission.thumbnail_url).where(
            MediaSubmission.user_id == user.id
        )
    )
    files = [url for row in rows.all() for url in row]
    files.append(user.avatar_url)

    await db.execute(delete(MagicLinkToken).where(MagicLinkToken.email == user.email))
    await db.delete(user)
    await db.commit()

    for url in files:
        delete_media_file(url)


@router.post("/{user_id}/block", status_code=204)
async def block_user(
    user_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user_id == user.id:
        raise HTTPException(status_code=400, detail="You can't block yourself")
    if not await db.scalar(select(User.id).where(User.id == user_id)):
        raise HTTPException(status_code=404, detail="User not found")

    await db.execute(
        insert(UserBlock)
        .values(id=uuid.uuid4(), blocker_id=user.id, blocked_id=user_id)
        .on_conflict_do_nothing(constraint="uq_user_block")
    )


@router.delete("/{user_id}/block", status_code=204)
async def unblock_user(
    user_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        delete(UserBlock).where(UserBlock.blocker_id == user.id, UserBlock.blocked_id == user_id)
    )


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
