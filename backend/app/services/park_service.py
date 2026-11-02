import uuid

from geoalchemy2.functions import ST_Distance, ST_DWithin, ST_SetSRID, ST_MakePoint, ST_X, ST_Y
from sqlalchemy import case, func, select, or_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skatepark import Skatepark

MIN_CELL_DEGREES = 0.0001
MAX_CELLS_ACROSS = 40


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
    ordering = [Skatepark.name]
    if q:
        escaped = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        matches = or_(
            Skatepark.name.ilike(pattern, escape="\\"),
            Skatepark.city.ilike(pattern, escape="\\"),
            Skatepark.state.ilike(pattern, escape="\\"),
            Skatepark.address.ilike(pattern, escape="\\"),
        )
        query = query.where(matches)
        count_query = count_query.where(matches)
        ordering = [
            case((Skatepark.name.like("Skatepark in %"), 1), else_=0),
            case(
                (Skatepark.name.ilike(f"{escaped}%", escape="\\"), 0),
                (Skatepark.name.ilike(pattern, escape="\\"), 1),
                else_=2,
            ),
            Skatepark.name,
        ]

    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(*ordering).offset((page - 1) * limit).limit(limit)
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


async def get_map_items(
    db: AsyncSession,
    south: float,
    west: float,
    north: float,
    east: float,
    cell: float,
    environment: str | None = None,
    is_free: bool | None = None,
) -> dict:
    boxes = [(west, east)] if west <= east else [(west, 180.0), (-180.0, east)]
    width = sum(box_east - box_west for box_west, box_east in boxes)
    params: dict = {
        "south": south,
        "north": north,
        "cell": max(cell, width / MAX_CELLS_ACROSS, MIN_CELL_DEGREES),
    }

    box_conditions = []
    for i, (box_west, box_east) in enumerate(boxes):
        box_conditions.append(f"geom && ST_MakeEnvelope(:w{i}, :south, :e{i}, :north, 4326)")
        params[f"w{i}"] = box_west
        params[f"e{i}"] = box_east

    conditions = [f"({' OR '.join(box_conditions)})"]
    if environment:
        conditions.append("environment = :environment")
        params["environment"] = environment
    if is_free is not None:
        conditions.append("is_free = :is_free")
        params["is_free"] = is_free

    cells = (
        await db.execute(
            text(f"""
                SELECT
                    count(*) AS count,
                    avg(ST_Y(geom)) AS lat,
                    avg(ST_X(geom)) AS lng,
                    min(ST_Y(geom)) AS south,
                    max(ST_Y(geom)) AS north,
                    min(ST_X(geom)) AS west,
                    max(ST_X(geom)) AS east,
                    (array_agg(id))[1] AS first_id
                FROM skateparks
                WHERE {' AND '.join(conditions)}
                GROUP BY floor(ST_X(geom) / :cell), floor(ST_Y(geom) / :cell)
            """),
            params,
        )
    ).mappings().all()

    clusters = [
        {key: row[key] for key in ("count", "lat", "lng", "south", "north", "west", "east")}
        for row in cells
        if row["count"] > 1
    ]

    single_ids = [row["first_id"] for row in cells if row["count"] == 1]
    parks = []
    if single_ids:
        rows = await db.execute(
            select(
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
            ).where(Skatepark.id.in_(single_ids))
        )
        parks = [dict(row) for row in rows.mappings().all()]

    return {"clusters": clusters, "parks": parks}


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
