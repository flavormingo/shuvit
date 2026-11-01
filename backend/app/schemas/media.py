import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


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
    contributor_name: str | None = None

    model_config = {"from_attributes": True}


class MediaApproveAction(BaseModel):
    action: Literal["approve", "reject"]


class MediaReportCreate(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class ReviewQueueItem(BaseModel):
    id: uuid.UUID
    park_id: uuid.UUID
    park_name: str
    user_id: uuid.UUID
    contributor_name: str | None = None
    media_type: str
    file_url: str
    thumbnail_url: str | None = None
    description: str | None = None
    status: str
    report_count: int = 0
    submitted_at: datetime
