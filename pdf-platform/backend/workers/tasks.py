"""Celery async tasks for PDF conversion.

Integration boundary:
  - Imports from the `algo` package (provided by the algorithm team).
  - Current code contains a placeholder; replace with real algo imports
    once the algo package is available.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.storage import get_absolute_path, save_upload
from app.models.task import Task
from workers.celery import celery_app

try:
    from algo.pipeline import convert as algo_convert
except ImportError:
    algo_convert = None  # placeholder; real algo not yet available


def _placeholder_convert(
    file_path: str,
    target_format: str,
    params: Dict[str, Any],
    output_dir: str,
) -> str:
    """Placeholder conversion when `algo` package is not installed."""
    raise NotImplementedError(
        "algo.pipeline.convert is not available. "
        "Install the algo package or implement the conversion logic."
    )


def _get_converter() -> Any:
    """Return the real converter or the placeholder."""
    if algo_convert is not None:
        return algo_convert
    return _placeholder_convert


async def _update_task_status(
    task_id: str,
    status: str,
    progress: float = 0.0,
    result_path: Optional[str] = None,
    result_filename: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    """Update the task status in the database."""
    async with async_session_factory() as db:
        result = await db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if task is None:
            return

        task.status = status
        task.progress = progress
        if result_path is not None:
            task.result_path = result_path
        if result_filename is not None:
            task.result_filename = result_filename
        if error_message is not None:
            task.error_message = error_message

        db.add(task)
        await db.commit()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def perform_conversion(
    self,
    file_path: str,
    target_format: str,
    params: Dict[str, Any],
    task_id: str,
) -> Dict[str, Any]:
    """Execute a PDF conversion as a Celery task.

    The task delegates to algo.pipeline.convert() which returns the
    output file path. That file is then recorded in the database.

    Args:
        file_path: Relative path to the uploaded source file.
        target_format: Target format identifier (e.g. 'docx', 'pptx').
        params: Conversion parameters (matching algo ConvertParams schema).
        task_id: UUID of the Task record in the database.

    Returns:
        Dict with 'status', 'result_path', 'result_filename' on success.
    """
    import asyncio
    import tempfile

    try:
        # Mark as processing
        asyncio.run(
            _update_task_status(
                task_id=task_id,
                status="processing",
                progress=0.1,
            )
        )

        converter = _get_converter()
        abs_path = get_absolute_path(file_path)

        if not abs_path.exists():
            raise FileNotFoundError(f"Source file not found: {abs_path}")

        # Create output directory and call the conversion pipeline
        output_dir = tempfile.mkdtemp(prefix="pdf_convert_")
        output_path: str = converter(
            file_path=str(abs_path),
            target_format=target_format,
            params=params,
            output_dir=output_dir,
        )

        # Read the output file
        import os
        with open(output_path, "rb") as f:
            output_bytes = f.read()

        ext = _format_to_extension(target_format)
        result_filename = f"converted_{task_id[:8]}{ext}"
        result_relative, _ = asyncio.run(
            save_upload(output_bytes, result_filename)
        )

        # Mark as completed
        asyncio.run(
            _update_task_status(
                task_id=task_id,
                status="completed",
                progress=1.0,
                result_path=result_relative,
                result_filename=result_filename,
            )
        )

        return {
            "status": "completed",
            "result_path": result_relative,
            "result_filename": result_filename,
        }

    except Exception as exc:
        asyncio.run(
            _update_task_status(
                task_id=task_id,
                status="failed",
                progress=0.0,
                error_message=str(exc),
            )
        )

        # Retry on transient errors (e.g. network / OOM)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            asyncio.run(
                _update_task_status(
                    task_id=task_id,
                    status="failed",
                    progress=0.0,
                    error_message=f"Max retries exceeded: {exc}",
                )
            )
            return {
                "status": "failed",
                "error": str(exc),
            }


def _format_to_extension(format_id: str) -> str:
    """Map format identifier to file extension (delegates to shared algo/utils)."""
    from algo.utils import get_extension
    return get_extension(format_id)
