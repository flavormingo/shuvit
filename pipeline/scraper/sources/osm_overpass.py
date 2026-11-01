import logging

import httpx

from pipeline.scraper.sources.base import RawPark, Source

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


class OverpassSource(Source):
    name = "osm"

    async def fetch(
        self,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> list[RawPark]:
        """Fetch skateparks from OpenStreetMap via Overpass API.

        bbox: (south, west, north, east) - defaults to Houston, TX area
        """
        if bbox is None:
            # Houston metropolitan area
            bbox = (29.5, -95.8, 30.1, -95.0)

        south, west, north, east = bbox
        query = f"""
        [out:json][timeout:60];
        (
          node["leisure"="pitch"]["sport"="skateboard"]({south},{west},{north},{east});
          way["leisure"="pitch"]["sport"="skateboard"]({south},{west},{north},{east});
          node["leisure"="skatepark"]({south},{west},{north},{east});
          way["leisure"="skatepark"]({south},{west},{north},{east});
          node["sport"="skateboard"]({south},{west},{north},{east});
          way["sport"="skateboard"]({south},{west},{north},{east});
        );
        out center body;
        """

        logger.info(f"Querying Overpass for bbox: {bbox}")

        import asyncio
        async with httpx.AsyncClient(timeout=120) as client:
            for attempt in range(3):
                resp = await client.post(OVERPASS_URL, data={"data": query})
                if resp.status_code == 429 or resp.status_code >= 500:
                    wait = (attempt + 1) * 15
                    logger.warning(f"Overpass returned {resp.status_code}, retrying in {wait}s...")
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                break
            data = resp.json()

        parks = []
        for element in data.get("elements", []):
            tags = element.get("tags", {})

            # Get coordinates (center for ways)
            if element["type"] == "way" and "center" in element:
                lat = element["center"]["lat"]
                lng = element["center"]["lon"]
            elif element["type"] == "node":
                lat = element["lat"]
                lng = element["lon"]
            else:
                continue

            name = tags.get("name") or tags.get("description")
            if not name:
                logger.debug(f"Skipping unnamed park at {lat:.4f}, {lng:.4f}")
                continue

            park = RawPark(
                name=name,
                lat=lat,
                lng=lng,
                address=tags.get("addr:street") or None,
                city=tags.get("addr:city") or None,
                state=tags.get("addr:state") or None,
                country=tags.get("addr:country", "US"),
                zip_code=tags.get("addr:postcode") or None,
                park_type=self._classify_type(tags),
                environment=self._classify_indoor_outdoor(tags),
                surface=tags.get("surface"),
                lighting=tags.get("lit") == "yes" if tags.get("lit") else None,
                is_free=tags.get("fee") != "yes",
                features={},
                description=tags.get("description"),
                source="osm",
                source_id=f"osm-{element['type']}-{element['id']}",
                metadata=tags,
            )
            parks.append(park)

        logger.info(f"Found {len(parks)} skateparks from OSM")
        return parks

    def _classify_indoor_outdoor(self, tags: dict) -> str:
        """Classify as indoor, outdoor, or both."""
        indoor_tag = tags.get("indoor", "")
        building_tag = tags.get("building", "")
        covered_tag = tags.get("covered", "")
        location_tag = tags.get("location", "")
        name = tags.get("name", "").lower()
        desc = tags.get("description", "").lower()
        combined = f"{name} {desc}"

        is_indoor = (
            indoor_tag == "yes"
            or building_tag not in ("", "no")
            or location_tag == "indoor"
            or "indoor" in combined
        )
        is_outdoor = (
            indoor_tag == "no"
            or location_tag == "outdoor"
            or "outdoor" in combined
            or covered_tag == "no"
        )

        if is_indoor and is_outdoor:
            return "both"
        if is_indoor:
            return "indoor"
        # Default to outdoor — most skateparks are
        return "outdoor"

    def _classify_type(self, tags: dict) -> str | None:
        name = tags.get("name", "").lower()
        desc = tags.get("description", "").lower()
        combined = f"{name} {desc}"

        if "diy" in combined:
            return "diy"
        if "transition" in combined or "bowl" in combined or "vert" in combined:
            return "transition"
        if "street" in combined:
            return "street"
        return "mixed"
