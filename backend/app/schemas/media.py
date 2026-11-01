import uuid
from datetime import datetime

from pydantic import BaseModel


class MediaSubmissionOut(BaseModel):
    id: uuid.UUID
    park_id: uuid.UUID
    user_id: uuid.UUID
    media_type: str
    file_url: str
    thumbnail_url: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    status: str = "pending"
    submitted_at: datetime

    model_config = {"from_attributes": True}


class MediaApproveAction(BaseModel):
    action: str  # "approve" or "reject"
