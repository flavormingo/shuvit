import uuid
from datetime import datetime

from pydantic import BaseModel


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None = None
    avatar_url: str | None = None
    is_admin: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    display_name: str | None = None


class UserProfile(BaseModel):
    id: uuid.UUID
    display_name: str | None = None
    avatar_url: str | None = None
    approved_count: int = 0
    parks_count: int = 0
    rank: str = "Rookie"

    model_config = {"from_attributes": True}
