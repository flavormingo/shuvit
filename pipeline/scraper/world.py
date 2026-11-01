import asyncio
import json
import logging
import time
from dataclasses import asdict
from pathlib import Path

from pipeline.scraper.sources.base import RawPark
from pipeline.scraper.sources.osm_overpass import (
    OverpassError,
    OverpassSource,
    OverpassUnavailable,
)

logger = logging.getLogger(__name__)

TILE_DEGREES = 30
MIN_TILE_DEGREES = 3.75
MIN_LATITUDE = -60
MAX_LATITUDE = 84
SECONDS_BETWEEN_QUERIES = 10
CACHE_MAX_AGE_SECONDS = 6 * 24 * 3600


def world_tiles() -> list[tuple[float, float, float, float]]:
    tiles = []
    for south in range(MIN_LATITUDE, MAX_LATITUDE, TILE_DEGREES):
        for west in range(-180, 180, TILE_DEGREES):
            tiles.append((south, west, min(south + TILE_DEGREES, MAX_LATITUDE), west + TILE_DEGREES))
    return tiles


def split_tile(tile: tuple[float, float, float, float]) -> list[tuple[float, float, float, float]]:
    south, west, north, east = tile
    mid_lat = (south + north) / 2
    mid_lng = (west + east) / 2
    return [
        (south, west, mid_lat, mid_lng),
        (south, mid_lng, mid_lat, east),
        (mid_lat, west, north, mid_lng),
        (mid_lat, mid_lng, north, east),
    ]


def unique_by_source_id(parks: list[RawPark]) -> list[RawPark]:
    return list({park.source_id: park for park in parks}.values())


class WorldFetcher:
    def __init__(self, cache_dir: Path, source: OverpassSource | None = None):
        self.cache_dir = cache_dir
        self.source = source or OverpassSource()
        self.failed_tiles: list[tuple[float, float, float, float]] = []
        self.overpass_unavailable = False
        cache_dir.mkdir(parents=True, exist_ok=True)

    async def fetch(self) -> list[RawPark]:
        parks: list[RawPark] = []
        tiles = world_tiles()
        for index, tile in enumerate(tiles, start=1):
            logger.info(f"Tile {index}/{len(tiles)}: {tile}")
            parks.extend(await self._fetch_tile(tile))
        return unique_by_source_id(parks)

    def _cached_parks(self, tile: tuple[float, float, float, float]) -> list[RawPark]:
        cached = self._read_cache(tile)
        if cached is not None:
            return cached
        if tile[2] - tile[0] <= MIN_TILE_DEGREES:
            return []
        return [park for part in split_tile(tile) for park in self._cached_parks(part)]

    def _cache_path(self, tile: tuple[float, float, float, float]) -> Path:
        return self.cache_dir / ("_".join(str(value) for value in tile) + ".json")

    def _read_cache(self, tile: tuple[float, float, float, float]) -> list[RawPark] | None:
        path = self._cache_path(tile)
        if not path.exists() or time.time() - path.stat().st_mtime > CACHE_MAX_AGE_SECONDS:
            return None
        return [RawPark(**row) for row in json.loads(path.read_text())]

    async def _fetch_tile(self, tile: tuple[float, float, float, float]) -> list[RawPark]:
        cached = self._read_cache(tile)
        if cached is not None:
            return cached

        if self.overpass_unavailable:
            self.failed_tiles.append(tile)
            return self._cached_parks(tile)

        try:
            parks = await self.source.fetch(tile)
        except OverpassUnavailable:
            logger.error("Overpass is unavailable; using cached tiles only for the rest of this run")
            self.overpass_unavailable = True
            self.failed_tiles.append(tile)
            return self._cached_parks(tile)
        except OverpassError:
            if tile[2] - tile[0] <= MIN_TILE_DEGREES:
                logger.error(f"Giving up on tile {tile}")
                self.failed_tiles.append(tile)
                return []
            logger.info(f"Splitting tile {tile}")
            parks = []
            for part in split_tile(tile):
                parks.extend(await self._fetch_tile(part))
            return parks

        await asyncio.sleep(SECONDS_BETWEEN_QUERIES)
        self._cache_path(tile).write_text(json.dumps([asdict(park) for park in parks]))
        return parks
