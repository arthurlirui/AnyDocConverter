"""
Conversion API endpoints.

- POST /api/v1/convert — one-shot: upload -> convert (frontend-facing)
- POST /api/v1/convert/sync — synchronous conversion for local dev (no Celery)
- POST /api/v1/tasks/{task_id}/start — start (or restart) an existing task
"""

from __future__ import annotations

import json
import shutil
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


def _build_task_result(task: Task) -> dict | None:
    """Build the standard `result` payload for a completed task.

    The shape is consistent across all endpoints that return a `TaskResponse`:
      {"file_id": <task id>, "filename": ..., "path": <storage relative path>}

    Returns None when the task is not yet completed or has no result file.
    Note: `file_id` is intentionally the *task* id (the handle the download
    endpoint accepts), not the source File id — see backend/app/api/download.py.
    """
    if task.status == "completed" and task.result_path and task.result_filename:
        return {
            "file_id": str(task.id),
            "filename": task.result_filename,
            "path": task.result_path,
        }
    return None


async def _commit_and_enqueue(
    db: AsyncSession,
    task: Task,
    source_file: File,
    params_payload: dict,
) -> None:
    """Commit `task`, then dispatch to Celery and record the celery task id.

    Committing *before* `.delay()` is critical: the worker opens its own DB
    session and selects the task by id. Under READ COMMITTED (Postgres
    default) an uncommitted row is invisible, so the worker would see
    `task is None` and silently return, leaving the task stuck in "queued".

    On broker failure the task is marked "failed" so the client is not left
    polling forever. The `celery_task_id` from the AsyncResult is recorded
    for future cancellation / inspection.
    """
    # Make the task row visible to the worker's separate session.
    await db.commit()

    try:
        from workers.tasks import perform_conversion
        async_result = perform_conversion.delay(
            file_path=source_file.storage_path,
            target_format=task.target_format,
            params=params_payload,
            task_id=str(task.id),
        )
        task.celery_task_id = async_result.id
        task.updated_at = datetime.now(timezone.utc)
        db.add(task)
        await db.commit()
    except Exception as exc:  # pragma: no cover - broker unreachable
        task.status = "failed"
        task.error_message = f"Failed to enqueue: {exc}"
        task.updated_at = datetime.now(timezone.utc)
        db.add(task)
        await db.commit()


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
    # StartConvertRequest.params has default_factory=ConvertParams, so it is
    # never None — the `if body.params else "{}"` branches are dead and removed.
    params_payload = body.params.model_dump(exclude_none=False)
    params_payload["output_format"] = body.target_format

    task = Task(
        id=str(uuid.uuid4()),
        file_id=file_id_str,
        target_format=body.target_format,
        params=json.dumps(body.params.model_dump(exclude_none=True)),
        status="queued",
        progress=0.0,
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)

    # Commit BEFORE dispatching so the worker can see the row (see
    # _commit_and_enqueue docstring). On broker failure the task is marked
    # "failed" inline.
    await _commit_and_enqueue(db, task, source_file, params_payload)
    await db.refresh(task)

    return TaskResponse(
        id=str(task.id),
        file_id=str(task.file_id),
        target_format=task.target_format,
        status=task.status,
        progress=task.progress,
        result=_build_task_result(task),
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

    Creates a task, processes it immediately in-process, and returns the
    result. Intended for local development when Redis is not running; in
    production use `POST /convert` so the work runs on the Celery worker.
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
        params=json.dumps(body.params.model_dump(exclude_none=True)),
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

        # backend.ConvertParams 是 algo.ConvertParams 的结构镜像，
        # 所以可以直接 dump 后载入 algo 类型。
        payload = body.params.model_dump(exclude_none=False)
        payload["output_format"] = body.target_format
        algo_params = AlgoParams(**payload)

        output_dir = tempfile.mkdtemp(prefix="pdf_convert_sync_")
        try:
            output_path = algo_convert(
                file_path=str(abs_path),
                target_format=body.target_format,
                params=algo_params,
                output_dir=output_dir,
            )

            # Read output and save to storage
            with open(output_path, "rb") as f:
                output_bytes = f.read()
        finally:
            # 无论成功失败都清理临时输出目录，避免磁盘泄漏
            shutil.rmtree(output_dir, ignore_errors=True)

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

    return TaskResponse(
        id=str(task.id),
        file_id=str(task.file_id),
        target_format=task.target_format,
        status=task.status,
        progress=task.progress,
        result=_build_task_result(task),
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
    """Start an already-created task with optional parameter overrides.

    This endpoint is the equivalent of `POST /convert` for tasks that already
    exist (e.g. created out-of-band, or being retried). It applies the
    overrides, commits, and dispatches to the Celery worker.
    """
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

    # StartTaskRequest.params is Optional[ConvertParams]; fall back to the
    # task's existing params if the caller omitted it.
    if body.params is not None:
        params_obj = body.params
    else:
        from app.schemas.task import ConvertParams
        try:
            params_obj = ConvertParams.model_validate_json(task.params or "{}")
        except Exception:
            params_obj = ConvertParams()

    params_payload = params_obj.model_dump(exclude_none=False)
    params_payload["output_format"] = body.target_format

    task.target_format = body.target_format
    task.params = json.dumps(params_obj.model_dump(exclude_none=True))
    task.status = "queued"
    task.progress = 0.0
    task.error_message = None
    task.celery_task_id = None
    task.updated_at = datetime.now(timezone.utc)

    db.add(task)
    await db.flush()
    await db.refresh(task)

    await _commit_and_enqueue(db, task, source_file, params_payload)
    await db.refresh(task)

    return TaskResponse(
        id=str(task.id),
        file_id=str(task.file_id),
        target_format=task.target_format,
        status=task.status,
        progress=task.progress,
        result=_build_task_result(task),
        error_message=task.error_message,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )
