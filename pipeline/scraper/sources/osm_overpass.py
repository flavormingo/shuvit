import asyncio
import logging
import re

import httpx

from pipeline.scraper.sources.base import RawPark, Source

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "Shuvit/1.0 (https://shuvit.app)"
HOUSTON_BBOX = (29.5, -95.8, 30.1, -95.0)
RETRY_ATTEMPTS = 3
SKATEBOARD_SPORT = '"sport"~"(^|;)skateboard(;|$)"'
NON_PARK_TAGS = ("shop", "office", "craft", "club")
NON_PARK_NAME = re.compile(r"(skate|board)\s*shop\b", re.IGNORECASE)


class OverpassError(Exception):
    pass


class OverpassUnavailable(OverpassError):
    pass


def build_query(bbox: tuple[float, float, float, float]) -> str:
    south, west, north, east = bbox
    area = f"({south},{west},{north},{east})"
    return f"""
    [out:json][timeout:180];
    (
      nwr["leisure"="skatepark"]{area};
      nwr["leisure"="pitch"][{SKATEBOARD_SPORT}]{area};
      nwr[{SKATEBOARD_SPORT}]["shop"!~"."]{area};
    );
    out center tags;
    """


def is_park(tags: dict) -> bool:
    if any(tag in tags for tag in NON_PARK_TAGS):
        return False
    return not NON_PARK_NAME.search(tags.get("name", ""))


def classify_environment(tags: dict) -> str:
    text = f"{tags.get('name', '')} {tags.get('description', '')}".lower()
    is_indoor = (
        tags.get("indoor") == "yes"
        or tags.get("building", "no") != "no"
        or tags.get("location") == "indoor"
        or re.search(r"\bindoor\b", text) is not None
    )
    is_outdoor = (
        tags.get("indoor") == "no"
        or tags.get("location") == "outdoor"
        or tags.get("covered") == "no"
        or re.search(r"\boutdoor\b", text) is not None
    )
    if is_indoor and is_outdoor:
        return "both"
    return "indoor" if is_indoor else "outdoor"


def classify_type(tags: dict) -> str | None:
    name = tags.get("name", "")
    description = tags.get("description", "")
    combined = f"{name} {description}"
    if re.search(r"\bdiy\b", combined, re.IGNORECASE):
        return "diy"
    if re.search(r"\b(bowl|transition|vert|mini ?ramp)\b", combined, re.IGNORECASE):
        return "transition"
    if re.search(r"\bstreet (plaza|course|park)\b|\bplaza\b", description, re.IGNORECASE):
        return "street"
    return None


def build_address(tags: dict) -> str | None:
    street = " ".join(p for p in (tags.get("addr:housenumber"), tags.get("addr:street")) if p)
    if not street:
        return None
    parts = (street, tags.get("addr:city"), tags.get("addr:state"), tags.get("addr:postcode"))
    return ", ".join(p for p in parts if p)


def element_to_park(element: dict) -> RawPark | None:
    tags = element.get("tags", {})
    if not is_park(tags):
        return None

    center = element.get("center") or element
    if "lat" not in center or "lon" not in center:
        return None

    return RawPark(
        name=tags.get("name", "").strip(),
        lat=center["lat"],
        lng=center["lon"],
        address=build_address(tags),
        city=tags.get("addr:city") or None,
        state=tags.get("addr:state") or None,
        country=tags.get("addr:country", "US"),
        zip_code=tags.get("addr:postcode") or None,
        park_type=classify_type(tags),
        environment=classify_environment(tags),
        surface=tags.get("surface"),
        lighting=tags.get("lit") == "yes" if tags.get("lit") else None,
        is_free=tags.get("fee") != "yes",
        description=tags.get("description"),
        source="osm",
        source_id=f"osm-{element['type']}-{element['id']}",
        metadata=tags,
    )


class OverpassSource(Source):
    name = "osm"

    async def fetch(
        self,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> list[RawPark]:
        bbox = bbox or HOUSTON_BBOX
        logger.info(f"Querying Overpass for bbox: {bbox}")

        data = await self._query(build_query(bbox))
        parks = [p for p in map(element_to_park, data.get("elements", [])) if p]

        logger.info(f"Found {len(parks)} skateparks from OSM in {bbox}")
        return parks

    async def _query(self, query: str) -> dict:
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=240, headers={"User-Agent": USER_AGENT}) as client:
            for attempt in range(1, RETRY_ATTEMPTS + 1):
                try:
                    response = await client.post(OVERPASS_URL, data={"data": query})
                    response.raise_for_status()
                    data = response.json()
                    if "timed out" in data.get("remark", "") or "out of memory" in data.get("remark", ""):
                        raise OverpassError(data["remark"])
                    return data
                except (httpx.HTTPError, ValueError, OverpassError) as exc:
                    last_error = exc
                    logger.warning(f"Overpass attempt {attempt} failed: {exc}")
                    if attempt < RETRY_ATTEMPTS:
                        await asyncio.sleep(attempt * 30)

        is_unreachable = isinstance(last_error, (httpx.ConnectError, httpx.ConnectTimeout))
        is_rate_limited = (
            isinstance(last_error, httpx.HTTPStatusError) and last_error.response.status_code == 429
        )
        if is_unreachable or is_rate_limited:
            raise OverpassUnavailable(str(last_error))
        raise OverpassError(f"Overpass failed after {RETRY_ATTEMPTS} attempts")
