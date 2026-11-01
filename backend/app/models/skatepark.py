import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, DateTime, Float, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Skatepark(Base):
    __tablename__ = "skateparks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(String(512))
    city: Mapped[str | None] = mapped_column(String(128))
    state: Mapped[str | None] = mapped_column(String(64))
    country: Mapped[str] = mapped_column(String(64), default="US")
    zip_code: Mapped[str | None] = mapped_column(String(16))
    geom = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    park_type: Mapped[str | None] = mapped_column(String(32))
    environment: Mapped[str | None] = mapped_column(String(16))
    features: Mapped[dict | None] = mapped_column(JSONB)
    rating: Mapped[float | None] = mapped_column(Float)
    difficulty: Mapped[str | None] = mapped_column(String(32))
    lighting: Mapped[bool | None] = mapped_column(Boolean)
    is_free: Mapped[bool] = mapped_column(Boolean, default=True)
    hours: Mapped[dict | None] = mapped_column(JSONB)
    surface: Mapped[str | None] = mapped_column(String(64))
    source: Mapped[str | None] = mapped_column(String(64))
    source_id: Mapped[str | None] = mapped_column(String(128))
    hero_image_url: Mapped[str | None] = mapped_column(String(512))
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    data_quality_score: Mapped[float | None] = mapped_column(Float)
    source_ids: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_skateparks_geom", "geom", postgresql_using="gist"),
        Index("idx_skateparks_city_state", "city", "state"),
        Index(
            "idx_skateparks_source",
            "source",
            "source_id",
            unique=True,
            postgresql_where=("source IS NOT NULL AND source_id IS NOT NULL"),
        ),
    )
