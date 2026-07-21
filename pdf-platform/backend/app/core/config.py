"""Application settings, loaded from environment variables.

All settings are read via Pydantic Settings (case-insensitive env lookup).
A `.env` file in the backend working directory is loaded automatically;
explicit env vars override `.env` values.

Environment variables
---------------------
- ``DATABASE_URL``: SQLAlchemy async URL. Use ``postgresql+asyncpg://…`` in
  Docker, ``sqlite+aiosqlite:///./pdfplatform.db`` for local dev (requires
  the ``aiosqlite`` package).
- ``REDIS_URL``: Redis URL used both as the Celery broker and the result
  backend (see :attr:`celery_broker_url` / :attr:`celery_result_backend`).
- ``UPLOAD_DIR``: Directory where source uploads and conversion results are
  stored. Created on app startup if missing.
- ``MAX_UPLOAD_SIZE_MB``: Max accepted upload size. NOTE: not currently
  enforced server-side — see README "Known limitations".
- ``CORS_ORIGINS``: Comma-separated list of allowed origins for the browser
  frontend.
- ``HOST`` / ``PORT`` / ``RELOAD``: Uvicorn launch args (used by dev.sh /
  Dockerfile CMD, not read inside the app process).
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the FastAPI backend and Celery worker."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/pdfplatform"

    # Redis (for Celery)
    redis_url: str = "redis://localhost:6379/0"

    # Storage
    upload_dir: Path = Path("/data/uploads")
    max_upload_size_mb: int = 50

    # CORS
    cors_origins: str = "http://localhost:3000"

    # Server (consumed by uvicorn launch, not by the app process itself)
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = True

    @property
    def cors_origin_list(self) -> List[str]:
        """``CORS_ORIGINS`` split into a list, with whitespace trimmed."""
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def max_upload_size_bytes(self) -> int:
        """``MAX_UPLOAD_SIZE_MB`` converted to bytes."""
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def celery_broker_url(self) -> str:
        """Celery broker URL — derived from :attr:`redis_url`."""
        return self.redis_url

    @property
    def celery_result_backend(self) -> str:
        """Celery result backend URL — derived from :attr:`redis_url`."""
        return self.redis_url


settings = Settings()
