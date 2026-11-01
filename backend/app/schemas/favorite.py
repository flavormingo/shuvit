import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.park import ParkOut


class FavoriteCreate(BaseModel):
    park_id: uuid.UUID


class FavoriteOut(BaseModel):
    id: uuid.UUID
    park_id: uuid.UUID
    created_at: datetime
    park: ParkOut | None = None

    model_config = {"from_attributes": True}
