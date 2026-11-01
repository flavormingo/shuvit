"""Reverse geocode parks to fill in missing address, city, state, zip."""

import asyncio
import logging

import httpx

from pipeline.scraper.sources.base import RawPark

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"

# US state name -> abbreviation
US_STATE_ABBREV = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY", "district of columbia": "DC",
}


def _normalize_state(state: str, country_code: str) -> str:
    """For US addresses, convert full state names to abbreviations.
    For international, leave as-is."""
    if country_code.upper() == "US":
        return US_STATE_ABBREV.get(state.lower(), state)
    return state


def _build_address(addr: dict) -> str:
    """Build a clean address from Nominatim structured fields.
    Works for any country: street number + street, city, state/province, zip.
    """
    # Street
    house = addr.get("house_number", "")
    road = addr.get("road", "")
    street = f"{house} {road}".strip()

    # City (try multiple fields for international support)
    city = (
        addr.get("city")
        or addr.get("town")
        or addr.get("village")
        or addr.get("municipality")
        or addr.get("city_district")
        or ""
    )

    # State/province (abbreviate for US)
    state = addr.get("state") or addr.get("province") or addr.get("region") or ""
    cc = addr.get("country_code", "").upper()
    if state and cc:
        state = _normalize_state(state, cc)

    # Zip
    postcode = addr.get("postcode", "")

    parts = [p for p in [street, city, state, postcode] if p]
    return ", ".join(parts)


async def reverse_geocode_parks(parks: list[RawPark]) -> list[RawPark]:
    """Fill in address fields using Nominatim reverse geocoding."""
    async with httpx.AsyncClient(
        timeout=15,
        headers={"User-Agent": "Shuvit/1.0 (skatepark locator app)"},
    ) as client:
        for i, park in enumerate(parks):
            try:
                resp = await client.get(
                    NOMINATIM_URL,
                    params={
                        "lat": park.lat,
                        "lon": park.lng,
                        "format": "json",
                        "addressdetails": 1,
                        "zoom": 18,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                addr = data.get("address", {})

                # Build clean address
                park.address = _build_address(addr)

                # Fill in structured fields for filtering/search
                if not park.city:
                    park.city = (
                        addr.get("city")
                        or addr.get("town")
                        or addr.get("village")
                        or addr.get("municipality")
                        or addr.get("city_district")
                    )
                cc = addr.get("country_code", "").upper()
                if cc:
                    park.country = cc

                if not park.state:
                    raw_state = addr.get("state") or addr.get("province") or addr.get("region")
                    if raw_state:
                        park.state = _normalize_state(raw_state, cc or park.country)
                # Also normalize existing state values
                elif park.state:
                    park.state = _normalize_state(park.state, cc or park.country)

                if not park.zip_code:
                    park.zip_code = addr.get("postcode")

                logger.debug(f"Geocoded {park.name}: {park.address}")

            except Exception:
                logger.warning(f"Failed to geocode {park.name} at {park.lat},{park.lng}")

            # Nominatim rate limit: max 1 req/sec
            if i < len(parks) - 1:
                await asyncio.sleep(1.1)

    return parks
