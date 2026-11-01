import logging
import re
from math import asin, cos, radians, sin, sqrt

from thefuzz import fuzz

from pipeline.scraper.sources.base import RawPark

logger = logging.getLogger(__name__)

DISTANCE_THRESHOLD_M = 200
NAME_SIMILARITY_THRESHOLD = 80

# Words to strip when comparing names
STRIP_WORDS = re.compile(
    r"\b(skatepark|skate\s*park|skateboard|park|houston|tx|texas)\b",
    re.IGNORECASE,
)


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance between two points in meters."""
    R = 6371000
    lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
    return 2 * R * asin(sqrt(a))


def normalize_name(name: str) -> str:
    """Normalize park name for comparison."""
    name = STRIP_WORDS.sub("", name)
    name = re.sub(r"[^\w\s]", "", name)
    name = re.sub(r"\s+", " ", name).strip().lower()
    return name


def _richness_score(park: RawPark) -> int:
    """Score how much metadata a park record has."""
    score = 0
    if park.address:
        score += 1
    if park.city:
        score += 1
    if park.description:
        score += 1
    if park.features:
        score += len(park.features)
    if park.surface:
        score += 1
    if park.lighting is not None:
        score += 1
    if park.hours:
        score += 1
    return score


def deduplicate(parks: list[RawPark]) -> list[RawPark]:
    """Remove duplicate parks using fuzzy name matching + geographic proximity."""
    if not parks:
        return []

    logger.info(f"Deduplicating {len(parks)} parks")

    # Sort by richness (keep the richest record)
    parks.sort(key=_richness_score, reverse=True)

    kept: list[RawPark] = []
    removed_indices: set[int] = set()

    for i, park_a in enumerate(parks):
        if i in removed_indices:
            continue

        norm_a = normalize_name(park_a.name)

        for j in range(i + 1, len(parks)):
            if j in removed_indices:
                continue

            park_b = parks[j]

            # Quick distance check
            dist = haversine_m(park_a.lat, park_a.lng, park_b.lat, park_b.lng)
            if dist > DISTANCE_THRESHOLD_M:
                continue

            # Name similarity check
            norm_b = normalize_name(park_b.name)
            similarity = fuzz.token_sort_ratio(norm_a, norm_b)

            if similarity >= NAME_SIMILARITY_THRESHOLD:
                logger.debug(
                    f"Dedup: '{park_a.name}' ~ '{park_b.name}' "
                    f"(sim={similarity}, dist={dist:.0f}m)"
                )
                removed_indices.add(j)

        kept.append(park_a)

    logger.info(f"Kept {len(kept)} parks after dedup (removed {len(removed_indices)})")
    return kept
