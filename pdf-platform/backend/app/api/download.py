from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.storage import get_absolute_path
from app.models.file import File
from app.models.task import Task

router = APIRouter()


@router.get(
    "/download/{file_id}",
    response_class=FileResponse,
    summary="Download a file by its ID",
)
async def download_file(
    file_id: str,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Download an uploaded file or a converted result file.

    The file_id can be:
    - A File record ID (for original uploads)
    - A Task ID (for converted results)
    """
    try:
        uid = uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file ID format")

    # Try as a File record first
    result = await db.execute(select(File).where(File.id == str(uid)))
    file_record = result.scalar_one_or_none()

    if file_record:
        abs_path = get_absolute_path(file_record.storage_path)
        if not abs_path.exists():
            raise HTTPException(status_code=404, detail="File not found on disk")
        return FileResponse(
            path=str(abs_path),
            filename=file_record.filename,
            media_type=file_record.mime_type or "application/octet-stream",
        )

    # Try as a Task result
    task_result = await db.execute(select(Task).where(Task.id == str(uid)))
    task = task_result.scalar_one_or_none()

    if task and task.status == "completed" and task.result_path:
        abs_path = get_absolute_path(task.result_path)
        if not abs_path.exists():
            raise HTTPException(status_code=404, detail="Result file not found on disk")
        media_type = _guess_mime_type(task.result_filename or task.target_format)
        return FileResponse(
            path=str(abs_path),
            filename=task.result_filename or f"output.{task.target_format}",
            media_type=media_type or "application/octet-stream",
        )

    raise HTTPException(status_code=404, detail="File not found")


def _guess_mime_type(filename_or_format: str) -> str | None:
    """Guess MIME type from a filename or format identifier."""
    ext = os.path.splitext(filename_or_format)[1].lower().lstrip(".")
    if not ext:
        ext = filename_or_format.lower()

    MIME_MAP = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "html": "text/html",
        "htm": "text/html",
        "md": "text/markdown",
        "markdown": "text/markdown",
        "txt": "text/plain",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
    }
    return MIME_MAP.get(ext)
