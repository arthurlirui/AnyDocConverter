"""Local filesystem storage for uploaded source files and conversion results.

Both source uploads and conversion outputs live under :attr:`settings.upload_dir`
(see :mod:`app.core.config`). Files are addressed by a UUID-derived relative
path so the absolute location can change between environments without
touching the database.

Security note
-------------
:func:`get_absolute_path` joins ``settings.upload_dir`` with a caller-supplied
relative path without a containment check. All current callers pass UUID-
generated paths, but any future code path that stores attacker-controlled
``storage_path`` / ``result_path`` values in the DB could escape the upload
directory. Defense-in-depth (a ``resolve()`` + prefix check) is worth adding
before exposing those columns to user input.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import aiofiles

from app.core.config import settings


async def ensure_upload_dir() -> None:
    """Create the upload directory (and parents) if it doesn't exist.

    Safe to call on every upload — ``exist_ok=True`` makes it a no-op once
    the directory exists.
    """
    settings.upload_dir.mkdir(parents=True, exist_ok=True)


def generate_storage_path(filename: str) -> tuple[Path, str]:
    """Generate a unique storage path for an uploaded file.

    The relative path is ``{uuid_hex}{ext}`` (no leading directory), so the
    upload directory stays flat and the relative path is safe to store in
    the DB and pass back to :func:`get_absolute_path`.

    Returns:
        ``(absolute_path, relative_path)`` — store the relative path in the
        DB and keep the absolute path for the immediate write.
    """
    ext = Path(filename).suffix
    file_id = uuid.uuid4().hex
    relative = f"{file_id}{ext}"
    return settings.upload_dir / relative, relative


async def save_upload(file_content: bytes, filename: str) -> tuple[str, Path]:
    """Save uploaded file bytes to disk and return the storage paths.

    Used for both the original upload and the conversion result (the worker
    writes the converted file via this same helper).

    Returns:
        ``(relative_path, absolute_path)`` — the relative path is what gets
        stored in ``File.storage_path`` / ``Task.result_path``.

    Note:
        The entire ``file_content`` is read into memory by the caller before
        this function is invoked. See README "Known limitations" re: the
        unbounded upload size.
    """
    await ensure_upload_dir()
    abs_path, relative = generate_storage_path(filename)
    async with aiofiles.open(abs_path, "wb") as f:
        await f.write(file_content)
    return relative, abs_path


def get_absolute_path(relative_path: str) -> Path:
    """Resolve a stored relative path back to an absolute filesystem path.

    Inverse of :func:`save_upload` / :func:`generate_storage_path`. Used by
    the worker to read the source file and by the download endpoint to
    serve the result.
    """
    return settings.upload_dir / relative_path


async def delete_file(relative_path: str) -> None:
    """Delete a stored file. No-op if the file is already gone.

    .. note::
        Currently unused — no endpoint cleans up files on task failure or
        deletion, so orphaned files accumulate in ``uploads/``. Wire this
        into a future cleanup endpoint or task-failure handler.
    """
    path = get_absolute_path(relative_path)
    if path.exists():
        path.unlink()
