import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.favorite import FavoriteCreate, FavoriteOut
from app.services import favorite_service

router = APIRouter(prefix="/favorites", tags=["favorites"])


@router.get("", response_model=list[FavoriteOut])
async def list_favorites(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await favorite_service.get_favorites(db, user.id)


@router.post("", response_model=dict, status_code=201)
async def add_favorite(
    body: FavoriteCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await favorite_service.add_favorite(db, user.id, body.park_id)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Already favorited")

    if not result:
        raise HTTPException(status_code=404, detail="Park not found")
    return result


@router.delete("/{park_id}", status_code=204)
async def remove_favorite(
    park_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    removed = await favorite_service.remove_favorite(db, user.id, park_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Favorite not found")
