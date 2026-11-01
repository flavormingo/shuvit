import logging
import os

import httpx

from pipeline.scraper.sources.base import RawPark, Source

logger = logging.getLogger(__name__)

PLACES_NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
PLACES_DETAIL_URL = "https://maps.googleapis.com/maps/api/place/details/json"


class GooglePlacesSource(Source):
    name = "google_places"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("GOOGLE_PLACES_API_KEY", "")

    async def fetch(
        self,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> list[RawPark]:
        """Fetch skateparks via Google Places API.

        bbox: (south, west, north, east) - used to compute center point
        """
        if not self.api_key:
            logger.warning("No Google Places API key configured, skipping")
            return []

        if bbox is None:
            # Houston center
            center_lat, center_lng = 29.7604, -95.3698
            radius = 50000  # 50km
        else:
            south, west, north, east = bbox
            center_lat = (south + north) / 2
            center_lng = (west + east) / 2
            from math import radians, cos, sqrt
            dlat = radians(north - south)
            dlng = radians(east - west) * cos(radians(center_lat))
            radius = int(sqrt(dlat**2 + dlng**2) * 6371000 / 2)
            radius = min(radius, 50000)

        parks = []
        next_page_token = None

        async with httpx.AsyncClient(timeout=30) as client:
            for page in range(3):  # max 3 pages (60 results)
                params = {
                    "key": self.api_key,
                    "keyword": "skatepark",
                    "location": f"{center_lat},{center_lng}",
                    "radius": radius,
                    "type": "park",
                }
                if next_page_token:
                    params = {"key": self.api_key, "pagetoken": next_page_token}

                resp = await client.get(PLACES_NEARBY_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

                for place in data.get("results", []):
                    loc = place["geometry"]["location"]
                    park = RawPark(
                        name=place["name"],
                        lat=loc["lat"],
                        lng=loc["lng"],
                        address=place.get("vicinity", ""),
                        source="google_places",
                        source_id=f"gp-{place['place_id']}",
                        metadata={
                            "place_id": place["place_id"],
                            "rating": place.get("rating"),
                            "user_ratings_total": place.get("user_ratings_total"),
                        },
                    )
                    if place.get("rating"):
                        park.features = {"google_rating": place["rating"]}
                    parks.append(park)

                next_page_token = data.get("next_page_token")
                if not next_page_token:
                    break

                # Google requires a short delay before using next_page_token
                import asyncio
                await asyncio.sleep(2)

        logger.info(f"Found {len(parks)} skateparks from Google Places")
        return parks
