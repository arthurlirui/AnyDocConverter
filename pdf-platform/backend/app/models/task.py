from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    file_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True
    )
    target_format: Mapped[str] = mapped_column(String(32), nullable=False)
    params: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="pending",
        index=True,
    )
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    result_path: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    result_filename: Mapped[str | None] = mapped_column(
        String(512), nullable=True, default=None
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    celery_task_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
