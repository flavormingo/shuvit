import hashlib
import json
import logging
import os
import re

import asyncpg

from pipeline.scraper.geocode import is_generated_name
from pipeline.scraper.sources.base import RawPark

logger = logging.getLogger(__name__)

UPSERT_SQL = """
    INSERT INTO skateparks (
        name, slug, description, address, city, state, country, zip_code,
        geom, park_type, environment, features, surface, lighting, is_free, hours,
        source, source_id, verified, data_quality_score
    ) VALUES (
        $1, $2, $3, $4, $5, $6, $7, $8,
        ST_SetSRID(ST_MakePoint($9, $10), 4326),
        $11, $12, $13::jsonb, $14, $15, $16, $17::jsonb,
        $18, $19, false, $20
    )
    ON CONFLICT (source, source_id)
        WHERE source IS NOT NULL AND source_id IS NOT NULL
    DO UPDATE SET
        name = COALESCE(EXCLUDED.name, skateparks.name),
        description = COALESCE(EXCLUDED.description, skateparks.description),
        address = COALESCE(skateparks.address, EXCLUDED.address),
        city = COALESCE(skateparks.city, EXCLUDED.city),
        state = COALESCE(skateparks.state, EXCLUDED.state),
        country = COALESCE(EXCLUDED.country, skateparks.country),
        zip_code = COALESCE(skateparks.zip_code, EXCLUDED.zip_code),
        geom = EXCLUDED.geom,
        park_type = COALESCE(EXCLUDED.park_type, skateparks.park_type),
        environment = COALESCE(EXCLUDED.environment, skateparks.environment),
        features = COALESCE(EXCLUDED.features, skateparks.features),
        surface = COALESCE(EXCLUDED.surface, skateparks.surface),
        lighting = COALESCE(EXCLUDED.lighting, skateparks.lighting),
        is_free = EXCLUDED.is_free,
        data_quality_score = EXCLUDED.data_quality_score,
        updated_at = now()
"""


MIN_KEEP_FRACTION = 0.8

PRUNE_SQL = """
    DELETE FROM skateparks
    WHERE source = 'osm'
      AND source_id <> ALL($1::text[])
      AND NOT EXISTS (SELECT 1 FROM favorites WHERE favorites.park_id = skateparks.id)
      AND NOT EXISTS (SELECT 1 FROM media_submissions WHERE media_submissions.park_id = skateparks.id)
"""


def slugify(name: str, city: str | None = None, source_id: str = "") -> str:
    text = "-".join(part for part in (name, city) if part).lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    suffix = hashlib.md5(source_id.encode()).hexdigest()[:6]
    return f"{text[:248]}-{suffix}"


def compute_quality_score(park: RawPark) -> float:
    fields = [
        not is_generated_name(park.name),
        park.address,
        park.city,
        park.state,
        park.description,
        park.park_type,
        park.surface,
    ]
    return round(sum(1 for field in fields if field) / len(fields), 2)


def _clip(value: str | None, length: int) -> str | None:
    return value[:length] if value else None


def upsert_values(park: RawPark) -> tuple:
    return (
        park.name[:255],
        slugify(park.name, park.city, park.source_id),
        park.description,
        _clip(park.address, 512),
        _clip(park.city, 128),
        _clip(park.state, 64),
        _clip(park.country, 64),
        _clip(park.zip_code, 16),
        park.lng,
        park.lat,
        park.park_type,
        park.environment,
        json.dumps(park.features) if park.features else None,
        _clip(park.surface, 64),
        park.lighting,
        park.is_free,
        json.dumps(park.hours) if park.hours else None,
        park.source,
        park.source_id,
        compute_quality_score(park),
    )


def _connection_url(database_url: str | None) -> str:
    db_url = database_url or os.environ.get(
        "DATABASE_URL", "postgresql://shuvit:shuvit@localhost:5432/shuvit"
    )
    return db_url.replace("postgresql+asyncpg://", "postgresql://")


async def prune_parks(keep_source_ids: set[str], database_url: str | None = None) -> int:
    conn = await asyncpg.connect(_connection_url(database_url))
    try:
        existing = await conn.fetchval("SELECT count(*) FROM skateparks WHERE source = 'osm'")
        if len(keep_source_ids) < existing * MIN_KEEP_FRACTION:
            raise ValueError(
                f"Refusing to prune: fetched {len(keep_source_ids)} parks but {existing} exist"
            )
        result = await conn.execute(PRUNE_SQL, list(keep_source_ids))
    finally:
        await conn.close()
    return int(result.split()[-1])


async def load_parks(parks: list[RawPark], database_url: str | None = None) -> int:
    conn = await asyncpg.connect(_connection_url(database_url))
    logger.info(f"Loading {len(parks)} parks into database")

    count = 0
    try:
        for park in parks:
            try:
                await conn.execute(UPSERT_SQL, *upsert_values(park))
                count += 1
            except asyncpg.PostgresError:
                logger.exception(f"Skipping {park.source_id}")
    finally:
        await conn.close()

    logger.info(f"Loaded {count} of {len(parks)} parks")
    return count
