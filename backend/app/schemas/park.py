import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ParkOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    lat: float
    lng: float
    city: str | None = None
    state: str | None = None
    country: str = "US"
    park_type: str | None = None
    environment: str | None = None
    rating: float | None = None
    difficulty: str | None = None
    is_free: bool = True
    hero_image_url: str | None = None
    verified: bool = False

    model_config = {"from_attributes": True}


class ParkNearOut(ParkOut):
    distance_km: float = 0.0


class ParkDetail(ParkOut):
    description: str | None = None
    address: str | None = None
    zip_code: str | None = None
    features: dict | None = None
    lighting: bool | None = None
    hours: dict | None = None
    surface: str | None = None
    data_quality_score: float | None = None
    created_at: datetime
    updated_at: datetime
    media: list = Field(default_factory=list)


class ParkCluster(BaseModel):
    count: int
    lat: float
    lng: float
    south: float
    north: float
    west: float
    east: float


class ParkMapOut(BaseModel):
    clusters: list[ParkCluster]
    parks: list[ParkOut]
