"""
Conversion API endpoints.

- POST /api/v1/convert — one-shot: upload -> convert (frontend-facing)
- POST /api/v1/tasks/{task_id}/start — start an already-created task
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.file import File
from app.models.task import Task
from app.schemas.task import (
    StartTaskRequest,
    StartConvertRequest,
    TaskResponse,
)

router = APIRouter()


@router.post(
    "/convert",
    response_model=TaskResponse,
    status_code=201,
    summary="Upload-then-convert in one call",
)
async def create_and_start_conversion(
    body: StartConvertRequest,
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """Create a conversion task and queue it immediately."""
    file_id_str = body.file_id
    result = await db.execute(select(File).where(File.id == file_id_str))
    source_file = result.scalar_one_or_none()
    if not source_file:
        raise HTTPException(status_code=404, detail="Source file not found")

    # Validate target format
    from app.api.formats import _KNOWN_FORMATS
    valid_formats = {f.id for f in _KNOWN_FORMATS}
    if body.target_format not in valid_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported target format: {body.target_format}. "
                   f"Supported: {', '.join(sorted(valid_formats))}",
        )

    # Create task
    now = datetime.now(timezone.utc)
    task = Task(
        id=str(uuid.uuid4()),
        file_id=file_id_str,
        target_format=body.target_format,
        params=json.dumps(body.params.model_dump(exclude_none=True)) if body.params else "{}",
        status="queued",
        progress=0.0,
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)

    return TaskResponse(
        id=str(task.id),
        file_id=str(task.file_id),
        target_format=task.target_format,
        status=task.status,
        progress=task.progress,
        result={"params": task.params} if task.params else None,
        error_message=task.error_message,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.post(
    "/tasks/{task_id}/start",
    response_model=TaskResponse,
    summary="Start (or restart) an existing conversion task",
)
async def start_existing_conversion(
    task_id: str,
    body: StartTaskRequest,
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """Start an already-created task with optional parameter overrides."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    from app.api.formats import _KNOWN_FORMATS
    valid_formats = {f.id for f in _KNOWN_FORMATS}
    if body.target_format not in valid_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format: {body.target_format}",
        )

    file_result = await db.execute(select(File).where(File.id == task.file_id))
    source_file = file_result.scalar_one_or_none()
    if not source_file:
        raise HTTPException(status_code=404, detail="Source file not found")

    task.target_format = body.target_format
    task.params = json.dumps(body.params.model_dump(exclude_none=True)) if body.params else "{}"
    task.status = "queued"
    task.progress = 0.0
    task.error_message = None
    task.updated_at = datetime.now(timezone.utc)

    db.add(task)
    await db.flush()
    await db.refresh(task)

    return TaskResponse(
        id=str(task.id),
        file_id=str(task.file_id),
        target_format=task.target_format,
        status=task.status,
        progress=task.progress,
        result={"params": task.params} if task.params else None,
        error_message=task.error_message,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )
