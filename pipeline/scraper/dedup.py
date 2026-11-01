import logging
import re
from collections import defaultdict
from math import asin, cos, radians, sin, sqrt

from thefuzz import fuzz

from pipeline.scraper.sources.base import RawPark

logger = logging.getLogger(__name__)

DISTANCE_THRESHOLD_M = 200
NAME_SIMILARITY_THRESHOLD = 80
GRID_CELL_DEGREES = 0.01

STRIP_WORDS = re.compile(r"\b(skatepark|skate\s*park|skateboard|park)\b", re.IGNORECASE)


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371000
    lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
    return 2 * R * asin(sqrt(a))


def normalize_name(name: str) -> str:
    name = STRIP_WORDS.sub("", name)
    name = re.sub(r"[^\w\s]", "", name)
    return re.sub(r"\s+", " ", name).strip().lower()


def _richness_score(park: RawPark) -> int:
    score = 3 if park.name else 0
    for value in (park.address, park.city, park.description, park.surface, park.hours):
        if value:
            score += 1
    if park.lighting is not None:
        score += 1
    if park.features:
        score += len(park.features)
    return score


def _cell(park: RawPark) -> tuple[int, int]:
    return int(park.lat // GRID_CELL_DEGREES), int(park.lng // GRID_CELL_DEGREES)


def _is_duplicate(keeper: RawPark, candidate: RawPark) -> bool:
    if haversine_m(keeper.lat, keeper.lng, candidate.lat, candidate.lng) > DISTANCE_THRESHOLD_M:
        return False
    if not keeper.name or not candidate.name:
        return True
    similarity = fuzz.token_sort_ratio(normalize_name(keeper.name), normalize_name(candidate.name))
    return similarity >= NAME_SIMILARITY_THRESHOLD


def deduplicate(parks: list[RawPark]) -> list[RawPark]:
    logger.info(f"Deduplicating {len(parks)} parks")

    kept_by_cell: dict[tuple[int, int], list[RawPark]] = defaultdict(list)
    kept: list[RawPark] = []

    for park in sorted(parks, key=_richness_score, reverse=True):
        lat_cell, lng_cell = _cell(park)
        neighbors = (
            other
            for dlat in (-1, 0, 1)
            for dlng in (-1, 0, 1)
            for other in kept_by_cell.get((lat_cell + dlat, lng_cell + dlng), ())
        )
        if any(_is_duplicate(other, park) for other in neighbors):
            continue
        kept_by_cell[(lat_cell, lng_cell)].append(park)
        kept.append(park)

    logger.info(f"Kept {len(kept)} parks after dedup (removed {len(parks) - len(kept)})")
    return kept
