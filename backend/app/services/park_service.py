import uuid

from geoalchemy2.functions import ST_Distance, ST_DWithin, ST_SetSRID, ST_MakePoint, ST_X, ST_Y
from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skatepark import Skatepark


async def list_parks(
    db: AsyncSession,
    page: int = 1,
    limit: int = 50,
    city: str | None = None,
    state: str | None = None,
    park_type: str | None = None,
    q: str | None = None,
) -> tuple[list[dict], int]:
    query = select(
        Skatepark.id,
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

    count_query = select(func.count(Skatepark.id))

    if city:
        query = query.where(func.lower(Skatepark.city) == city.lower())
        count_query = count_query.where(func.lower(Skatepark.city) == city.lower())
    if state:
        query = query.where(func.lower(Skatepark.state) == state.lower())
        count_query = count_query.where(func.lower(Skatepark.state) == state.lower())
    if park_type:
        query = query.where(Skatepark.park_type == park_type)
        count_query = count_query.where(Skatepark.park_type == park_type)
    if q:
        pattern = f"%{q}%"
        query = query.where(
            or_(Skatepark.name.ilike(pattern), Skatepark.address.ilike(pattern))
        )
        count_query = count_query.where(
            or_(Skatepark.name.ilike(pattern), Skatepark.address.ilike(pattern))
        )

    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(Skatepark.name).offset((page - 1) * limit).limit(limit)
    rows = (await db.execute(query)).all()

    parks = [
        {
            "id": r.id,
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
        }
        for r in rows
    ]
    return parks, total


async def get_nearby(
    db: AsyncSession,
    lat: float,
    lng: float,
    radius_km: float = 25,
    limit: int = 50,
) -> list[dict]:
    from sqlalchemy import text

    radius_m = radius_km * 1000

    query = text("""
        SELECT
            id, name, slug,
            ST_Y(geom) as lat,
            ST_X(geom) as lng,
            city, state, country, park_type, environment, rating, difficulty,
            is_free, hero_image_url, verified,
            ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography) / 1000 as distance_km
        FROM skateparks
        WHERE ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :radius_m)
        ORDER BY distance_km
        LIMIT :limit
    """)

    result = await db.execute(
        query, {"lat": lat, "lng": lng, "radius_m": radius_m, "limit": limit}
    )
    rows = result.all()
    return [
        {
            "id": r.id,
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
            "distance_km": round(r.distance_km, 2) if r.distance_km else 0,
        }
        for r in rows
    ]


async def get_in_bounds(
    db: AsyncSession,
    south: float,
    west: float,
    north: float,
    east: float,
    limit: int = 300,
) -> list[dict]:
    """Parks inside a map viewport. The best-documented parks win when there are too many."""
    from sqlalchemy import text

    boxes = [(west, east)] if west <= east else [(west, 180.0), (-180.0, east)]
    condition = " OR ".join(
        f"geom && ST_MakeEnvelope(:w{i}, :south, :e{i}, :north, 4326)" for i in range(len(boxes))
    )
    params: dict = {"south": south, "north": north, "limit": limit}
    for i, (box_west, box_east) in enumerate(boxes):
        params[f"w{i}"] = box_west
        params[f"e{i}"] = box_east

    query = text(f"""
        SELECT
            id, name, slug,
            ST_Y(geom) as lat,
            ST_X(geom) as lng,
            city, state, country, park_type, environment, rating, difficulty,
            is_free, hero_image_url, verified
        FROM skateparks
        WHERE {condition}
        ORDER BY data_quality_score DESC NULLS LAST, id
        LIMIT :limit
    """)
    rows = (await db.execute(query, params)).mappings().all()
    return [dict(row) for row in rows]


async def get_park(db: AsyncSession, park_id: uuid.UUID) -> dict | None:
    query = select(
        Skatepark,
        ST_Y(Skatepark.geom).label("lat"),
        ST_X(Skatepark.geom).label("lng"),
    ).where(Skatepark.id == park_id)

    row = (await db.execute(query)).first()
    if not row:
        return None

    park = row[0]
    return {
        "id": park.id,
        "name": park.name,
        "slug": park.slug,
        "lat": row.lat,
        "lng": row.lng,
        "description": park.description,
        "address": park.address,
        "city": park.city,
        "state": park.state,
        "country": park.country,
        "zip_code": park.zip_code,
        "park_type": park.park_type,
        "environment": park.environment,
        "features": park.features,
        "rating": park.rating,
        "difficulty": park.difficulty,
        "lighting": park.lighting,
        "is_free": park.is_free,
        "hours": park.hours,
        "surface": park.surface,
        "hero_image_url": park.hero_image_url,
        "verified": park.verified,
        "data_quality_score": park.data_quality_score,
        "created_at": park.created_at,
        "updated_at": park.updated_at,
        "media": [],
    }
