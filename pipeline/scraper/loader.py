import logging
import os
import re

import asyncpg

from pipeline.scraper.sources.base import RawPark

logger = logging.getLogger(__name__)


def _slugify(name: str, city: str | None = None, source_id: str = "") -> str:
    """Generate URL-friendly slug from name. Uses source_id suffix to guarantee uniqueness."""
    parts = [name]
    if city:
        parts.append(city)
    text = "-".join(parts).lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    # Append short hash of source_id to guarantee uniqueness
    if source_id:
        import hashlib
        suffix = hashlib.md5(source_id.encode()).hexdigest()[:6]
        text = f"{text}-{suffix}"
    return text[:255]


async def load_parks(parks: list[RawPark], database_url: str | None = None) -> int:
    """Upsert parks into PostgreSQL. Returns number of rows affected."""
    db_url = database_url or os.environ.get(
        "DATABASE_URL", "postgresql://shuvit:shuvit@localhost:5432/shuvit"
    )
    # asyncpg needs postgresql:// not postgresql+asyncpg://
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    conn = await asyncpg.connect(db_url)
    logger.info(f"Loading {len(parks)} parks into database")

    count = 0
    try:
        for park in parks:
            slug = _slugify(park.name, park.city, park.source_id)

            await conn.execute(
                """
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
                    address = COALESCE(EXCLUDED.address, skateparks.address),
                    city = COALESCE(EXCLUDED.city, skateparks.city),
                    state = COALESCE(EXCLUDED.state, skateparks.state),
                    park_type = COALESCE(EXCLUDED.park_type, skateparks.park_type),
                    environment = COALESCE(EXCLUDED.environment, skateparks.environment),
                    features = COALESCE(EXCLUDED.features, skateparks.features),
                    surface = COALESCE(EXCLUDED.surface, skateparks.surface),
                    lighting = COALESCE(EXCLUDED.lighting, skateparks.lighting),
                    updated_at = now()
                """,
                park.name,
                slug,
                park.description,
                park.address or None,
                park.city or None,
                park.state or None,
                park.country,
                park.zip_code or None,
                park.lng,  # ST_MakePoint(lng, lat)
                park.lat,
                park.park_type,
                park.environment,
                __import__("json").dumps(park.features) if park.features else None,
                park.surface,
                park.lighting,
                park.is_free,
                __import__("json").dumps(park.hours) if park.hours else None,
                park.source,
                park.source_id,
                _compute_quality_score(park),
            )
            count += 1
    except Exception:
        logger.exception("Error loading parks")
        raise
    finally:
        await conn.close()

    logger.info(f"Successfully loaded {count} parks")
    return count


def _compute_quality_score(park: RawPark) -> float:
    """Compute a 0-1 quality score based on data completeness."""
    fields = [
        park.name,
        park.address,
        park.city,
        park.state,
        park.description,
        park.park_type,
        park.surface,
    ]
    filled = sum(1 for f in fields if f)
    return round(filled / len(fields), 2)
