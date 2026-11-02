import asyncio
import logging
import re

import httpx

from pipeline.scraper.sources.base import RawPark
from pipeline.scraper.sources.osm_overpass import USER_AGENT, element_to_park

logger = logging.getLogger(__name__)

QLEVER_URL = "https://qlever.dev/api/osm-planet"
RETRY_ATTEMPTS = 3
KEY_PREFIX = "https://www.openstreetmap.org/wiki/Key:"
OSM_ID = re.compile(r"openstreetmap\.org/(node|way|relation)/(\d+)$")
WKT_COORDINATE = re.compile(r"(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)")

CANDIDATES = """
    { ?park osmkey:sport ?sport . FILTER(CONTAINS(?sport, "skateboard")) }
    UNION
    { ?park osmkey:leisure "skatepark" }
"""

PREFIXES = """
    PREFIX osmkey: <https://www.openstreetmap.org/wiki/Key:>
    PREFIX geo: <http://www.opengis.net/ont/geosparql#>
"""

TAGS_QUERY = f"""{PREFIXES}
    SELECT ?park ?key ?value WHERE {{
        {{ SELECT DISTINCT ?park WHERE {{ {CANDIDATES} }} }}
        ?park ?key ?value .
        FILTER(STRSTARTS(STR(?key), "{KEY_PREFIX}"))
    }}
"""

GEOMETRIES_QUERY = f"""{PREFIXES}
    SELECT ?park ?wkt WHERE {{
        {{ SELECT DISTINCT ?park WHERE {{ {CANDIDATES} }} }}
        ?park geo:hasGeometry/geo:asWKT ?wkt .
    }}
"""


def wkt_center(wkt: str) -> dict | None:
    coordinates = [(float(lon), float(lat)) for lon, lat in WKT_COORDINATE.findall(wkt)]
    if not coordinates:
        return None
    longitudes, latitudes = zip(*coordinates)
    return {
        "lat": (min(latitudes) + max(latitudes)) / 2,
        "lon": (min(longitudes) + max(longitudes)) / 2,
    }


def build_elements(tag_rows: list[dict], geometry_rows: list[dict]) -> list[dict]:
    tags_by_park: dict[str, dict] = {}
    for row in tag_rows:
        key = row["key"]["value"].removeprefix(KEY_PREFIX)
        tags_by_park.setdefault(row["park"]["value"], {})[key] = row["value"]["value"]

    elements = []
    for row in geometry_rows:
        uri = row["park"]["value"]
        identifier = OSM_ID.search(uri)
        center = wkt_center(row["wkt"]["value"])
        if not identifier or not center or uri not in tags_by_park:
            continue
        elements.append(
            {
                "type": identifier.group(1),
                "id": int(identifier.group(2)),
                "center": center,
                "tags": tags_by_park[uri],
            }
        )
    return elements


class QleverError(Exception):
    pass


class QleverSource:
    name = "osm"

    async def fetch_world(self) -> list[RawPark]:
        async with httpx.AsyncClient(timeout=600, headers={"User-Agent": USER_AGENT}) as client:
            tag_rows = await self._query(client, TAGS_QUERY)
            geometry_rows = await self._query(client, GEOMETRIES_QUERY)

        elements = build_elements(tag_rows, geometry_rows)
        parks = [park for park in map(element_to_park, elements) if park]
        logger.info(f"QLever returned {len(elements)} elements, {len(parks)} parks")
        if not parks:
            raise QleverError(
                f"QLever returned no parks ({len(tag_rows)} tag rows, {len(geometry_rows)} geometry rows)"
            )
        return parks

    async def _query(self, client: httpx.AsyncClient, query: str) -> list[dict]:
        for attempt in range(1, RETRY_ATTEMPTS + 1):
            try:
                response = await client.post(
                    QLEVER_URL,
                    data={"query": query},
                    headers={"Accept": "application/sparql-results+json"},
                )
                response.raise_for_status()
                return response.json()["results"]["bindings"]
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                logger.warning(f"QLever attempt {attempt} failed: {exc}")
                if attempt < RETRY_ATTEMPTS:
                    await asyncio.sleep(attempt * 30)
        raise QleverError(f"QLever failed after {RETRY_ATTEMPTS} attempts")
