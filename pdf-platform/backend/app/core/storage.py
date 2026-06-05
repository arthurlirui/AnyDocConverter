from __future__ import annotations

import uuid
from pathlib import Path

import aiofiles

from app.core.config import settings


async def ensure_upload_dir() -> None:
    """Create the upload directory if it doesn't exist."""
    settings.upload_dir.mkdir(parents=True, exist_ok=True)


def generate_storage_path(filename: str) -> tuple[Path, str]:
    """Generate a unique storage path for an uploaded file.

    Returns (absolute_path, relative_path).
    """
    ext = Path(filename).suffix
    file_id = uuid.uuid4().hex
    relative = f"{file_id}{ext}"
    return settings.upload_dir / relative, relative


async def save_upload(file_content: bytes, filename: str) -> tuple[str, Path]:
    """Save uploaded file bytes to disk.

    Returns (relative_path, absolute_path).
    """
    await ensure_upload_dir()
    abs_path, relative = generate_storage_path(filename)
    async with aiofiles.open(abs_path, "wb") as f:
        await f.write(file_content)
    return relative, abs_path


def get_absolute_path(relative_path: str) -> Path:
    """Get the absolute path for a stored file."""
    return settings.upload_dir / relative_path


async def delete_file(relative_path: str) -> None:
    """Delete a stored file."""
    path = get_absolute_path(relative_path)
    if path.exists():
        path.unlink()
