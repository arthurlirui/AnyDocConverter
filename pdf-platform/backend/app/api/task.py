from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.convert import _build_task_result
from app.core.database import get_db
from app.models.task import Task
from app.schemas.task import TaskResponse

router = APIRouter()


@router.get(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    summary="Get conversion task status and result",
)
async def get_task_status(
    task_id: str,
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """Return the current status, progress, and result of a conversion task."""
    try:
        uid = uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task ID format")

    result = await db.execute(select(Task).where(Task.id == str(uid)))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

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
