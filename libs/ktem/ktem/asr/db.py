"""Database table for registered speaker identities."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from ktem.db.engine import engine


class Base(DeclarativeBase):
    pass


class VoiceprintTable(Base):
    """Metadata for a voiceprint stored by the configured ASR provider."""

    __tablename__ = "asr_voiceprint"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: uuid.uuid4().hex
    )
    display_name: Mapped[str] = mapped_column(String, unique=True, index=True)
    provider_id: Mapped[str] = mapped_column(String, unique=True)
    sample_count: Mapped[int] = mapped_column(Integer, default=1)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now
    )


class ASRModelTable(Base):
    """Singleton configuration for the hospital realtime ASR service."""

    __tablename__ = "asr_model"

    id: Mapped[str] = mapped_column(String, primary_key=True, default="default")
    provider: Mapped[str] = mapped_column(String, default="mock")
    api_base_url: Mapped[str] = mapped_column(String, default="")
    api_key: Mapped[str] = mapped_column(String, default="")
    model: Mapped[str] = mapped_column(String, default="")
    timeout: Mapped[float] = mapped_column(Float, default=60.0)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now
    )


VoiceprintTable.metadata.create_all(engine)
