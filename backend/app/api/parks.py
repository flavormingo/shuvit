import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_optional
from app.database import get_db
from app.models.user import User
from app.schemas.park import ParkDetail, ParkMapOut, ParkNearOut, ParkOut
from app.services import park_service
from app.services.media_service import get_approved_media

router = APIRouter(prefix="/parks", tags=["parks"])


@router.get("", response_model=list[ParkOut])
async def list_parks(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    city: str | None = None,
    state: str | None = None,
    park_type: str | None = None,
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    parks, total = await park_service.list_parks(
        db, page=page, limit=limit, city=city, state=state, park_type=park_type, q=q
    )
    return parks


@router.get("/near", response_model=list[ParkNearOut])
async def parks_near(
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
    radius_km: float = Query(25, ge=0.1, le=200),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    return await park_service.get_nearby(db, lat=lat, lng=lng, radius_km=radius_km, limit=limit)


@router.get("/map", response_model=ParkMapOut)
async def parks_for_map(
    south: float = Query(ge=-90, le=90),
    west: float = Query(ge=-180, le=180),
    north: float = Query(ge=-90, le=90),
    east: float = Query(ge=-180, le=180),
    cell: float = Query(gt=0, le=90),
    environment: Literal["indoor", "outdoor", "both"] | None = None,
    is_free: bool | None = None,
    db: AsyncSession = Depends(get_db),
):
    return await park_service.get_map_items(
        db,
        south=south,
        west=west,
        north=north,
        east=east,
        cell=cell,
        environment=environment,
        is_free=is_free,
    )


@router.get("/{park_id}", response_model=ParkDetail)
async def get_park(
    park_id: uuid.UUID,
    viewer: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    park = await park_service.get_park(db, park_id)
    if not park:
        raise HTTPException(status_code=404, detail="Park not found")

    park["media"] = await get_approved_media(db, park_id, viewer.id if viewer else None)
    return park
