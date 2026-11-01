from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class RawPark:
    name: str
    lat: float
    lng: float
    address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str = "US"
    zip_code: str | None = None
    park_type: str | None = None
    environment: str | None = None
    features: dict | None = None
    surface: str | None = None
    lighting: bool | None = None
    is_free: bool = True
    hours: dict | None = None
    description: str | None = None
    source: str = ""
    source_id: str = ""
    metadata: dict = field(default_factory=dict)


class Source(ABC):
    name: str = "base"

    @abstractmethod
    async def fetch(
        self,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> list[RawPark]:
        """Fetch skateparks within bounding box (south, west, north, east)."""
        ...
