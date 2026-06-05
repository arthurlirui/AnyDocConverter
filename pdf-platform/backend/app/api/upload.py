from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.storage import save_upload
from app.models.file import File
from app.schemas.task import UploadResponse

router = APIRouter()


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=201,
    summary="Upload a file for conversion",
)
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    db: AsyncSession = Depends(get_db),
) -> UploadResponse:
    """Upload a file to the platform for subsequent conversion."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    content = await file.read()

    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    mime_type = file.content_type or "application/octet-stream"

    # Save to disk
    relative_path, _ = await save_upload(content, file.filename)

    # Create DB record
    file_record = File(
        id=str(uuid.uuid4()),
        filename=file.filename,
        size=len(content),
        mime_type=mime_type,
        storage_path=relative_path,
    )
    db.add(file_record)
    await db.flush()
    await db.refresh(file_record)

    return UploadResponse(
        file_id=str(file_record.id),
        filename=file_record.filename,
        size=file_record.size,
    )
