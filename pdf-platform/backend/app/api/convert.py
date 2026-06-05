"""
Conversion API endpoints.

- POST /api/v1/convert — one-shot: upload -> convert (frontend-facing)
- POST /api/v1/tasks/{task_id}/start — start an already-created task
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.storage import get_absolute_path, save_upload
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
    "/convert/sync",
    response_model=TaskResponse,
    status_code=201,
    summary="Convert synchronously (bypasses Celery, for local dev)",
)
async def convert_sync(
    body: StartConvertRequest,
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """Convert a PDF synchronously — no Celery/Redis needed.

    Creates a task, processes it immediately, and returns the result.
    Only available when CELERY_ALWAYS_EAGER is set or Redis is not configured.
    """
    file_id_str = body.file_id
    result = await db.execute(select(File).where(File.id == file_id_str))
    source_file = result.scalar_one_or_none()
    if not source_file:
        raise HTTPException(status_code=404, detail="Source file not found")

    from app.api.formats import _KNOWN_FORMATS
    valid_formats = {f.id for f in _KNOWN_FORMATS}
    if body.target_format not in valid_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported target format: {body.target_format}."
                   f" Supported: {', '.join(sorted(valid_formats))}",
        )

    # Create task
    now = datetime.now(timezone.utc)
    task = Task(
        id=str(uuid.uuid4()),
        file_id=file_id_str,
        target_format=body.target_format,
        params=json.dumps(body.params.model_dump(exclude_none=True)) if body.params else "{}",
        status="processing",
        progress=0.1,
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)

    try:
        # Run conversion synchronously
        abs_path = get_absolute_path(source_file.storage_path)
        if not abs_path.exists():
            raise FileNotFoundError(f"Source file not found: {abs_path}")

        from algo.pipeline import convert as algo_convert
        from algo.models.params import ConvertParams as AlgoParams
        from algo.utils import get_extension

        # Map backend params to algo params
        algo_params = AlgoParams()
        if body.params:
            algo_params = algo_params.model_copy(update={
                "output_format": body.target_format,
            })

        output_dir = tempfile.mkdtemp(prefix="pdf_convert_sync_")
        output_path = algo_convert(
            file_path=str(abs_path),
            target_format=body.target_format,
            params=algo_params,
            output_dir=output_dir,
        )

        # Read output and save to storage
        with open(output_path, "rb") as f:
            output_bytes = f.read()

        ext = get_extension(body.target_format)
        result_filename = f"converted_{task.id[:8]}{ext}"
        result_relative, _ = await save_upload(output_bytes, result_filename)

        # Update task
        task.status = "completed"
        task.progress = 1.0
        task.result_path = result_relative
        task.result_filename = result_filename
        task.updated_at = datetime.now(timezone.utc)

    except Exception as exc:
        task.status = "failed"
        task.progress = 0.0
        task.error_message = str(exc)
        task.updated_at = datetime.now(timezone.utc)

    db.add(task)
    await db.flush()
    await db.refresh(task)

    task_result = None
    if task.status == "completed" and task.result_path and task.result_filename:
        task_result = {
            "file_id": str(task.id),
            "filename": task.result_filename,
            "path": task.result_path,
        }

    return TaskResponse(
        id=str(task.id),
        file_id=str(task.file_id),
        target_format=task.target_format,
        status=task.status,
        progress=task.progress,
        result=task_result,
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
