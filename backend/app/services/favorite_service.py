import uuid

from geoalchemy2.functions import ST_X, ST_Y
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.favorite import Favorite
from app.models.skatepark import Skatepark


async def get_favorites(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    query = (
        select(
            Favorite.id,
            Favorite.park_id,
            Favorite.created_at,
            Skatepark.name,
            Skatepark.slug,
            ST_Y(Skatepark.geom).label("lat"),
            ST_X(Skatepark.geom).label("lng"),
            Skatepark.city,
            Skatepark.state,
            Skatepark.country,
            Skatepark.park_type,
            Skatepark.environment,
            Skatepark.rating,
            Skatepark.difficulty,
            Skatepark.is_free,
            Skatepark.hero_image_url,
            Skatepark.verified,
        )
        .join(Skatepark, Favorite.park_id == Skatepark.id)
        .where(Favorite.user_id == user_id)
        .order_by(Favorite.created_at.desc())
    )

    rows = (await db.execute(query)).all()
    return [
        {
            "id": r.id,
            "park_id": r.park_id,
            "created_at": r.created_at,
            "park": {
                "id": r.park_id,
                "name": r.name,
                "slug": r.slug,
                "lat": r.lat,
                "lng": r.lng,
                "city": r.city,
                "state": r.state,
                "country": r.country,
                "park_type": r.park_type,
                "environment": r.environment,
                "rating": r.rating,
                "difficulty": r.difficulty,
                "is_free": r.is_free,
                "hero_image_url": r.hero_image_url,
                "verified": r.verified,
            },
        }
        for r in rows
    ]


async def add_favorite(
    db: AsyncSession, user_id: uuid.UUID, park_id: uuid.UUID
) -> dict | None:
    # Check park exists
    park = await db.execute(select(Skatepark.id).where(Skatepark.id == park_id))
    if not park.scalar_one_or_none():
        return None

    fav = Favorite(user_id=user_id, park_id=park_id)
    db.add(fav)
    await db.flush()
    return {"id": fav.id, "park_id": park_id, "created_at": fav.created_at}


async def remove_favorite(
    db: AsyncSession, user_id: uuid.UUID, park_id: uuid.UUID
) -> bool:
    result = await db.execute(
        delete(Favorite).where(
            Favorite.user_id == user_id, Favorite.park_id == park_id
        )
    )
    return result.rowcount > 0
