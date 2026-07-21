"""Pydantic request / response schemas for the conversion API.

The parameter models (:class:`OCRParams`, :class:`LayoutParams`,
:class:`ImageParams`, :class:`FontParams`, :class:`ConvertParams`) are a
**structural mirror** of ``algo/models/params.py``. They must stay field-for-
field compatible so the backend can ``model_dump`` them and re-load into the
algo ``ConvertParams`` without lossy translation. When you add a field to
one side, add it to the other in the same change.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Conversion parameters (mirror of algo/models/params.py) ─────────────
#
# These types must stay structurally identical to algo.models.params.ConvertParams
# so that the backend API can pass them straight through to the conversion
# pipeline without lossy field translation.


class OCRParams(BaseModel):
    enabled: bool = Field(False, description="Enable OCR enhancement")
    engine: str = Field("paddle", description="OCR engine: paddle / tesseract")
    language: str = Field("ch", description="OCR language code: ch/en/japan/korean/chinese_cht")
    min_confidence: float = Field(0.45, ge=0.0, le=1.0, description="Min confidence threshold")
    enhance_image: bool = Field(False, description="Enable difficult-image preprocessing")
    enhance_mode: str = Field("standard", description="Preprocess mode: standard / hard")
    upscale_factor: float = Field(1.0, ge=1.0, le=4.0, description="Upscale factor before OCR")
    contrast: float = Field(1.15, ge=0.5, le=3.0, description="Contrast enhancement factor")
    sharpness: float = Field(1.05, ge=0.5, le=3.0, description="Sharpness enhancement factor")
    binarize: bool = Field(False, description="Binarize image before OCR")


class LayoutParams(BaseModel):
    detect_tables: bool = Field(True, description="Detect tables")
    detect_images: bool = Field(True, description="Detect images")
    detect_headers_footers: bool = Field(True, description="Detect headers & footers")
    reading_order: bool = Field(True, description="Restore reading order")


class ImageParams(BaseModel):
    quality: int = Field(85, ge=1, le=100, description="JPG quality")
    max_width: Optional[int] = Field(None, ge=1, description="Max output width in px")
    max_height: Optional[int] = Field(None, ge=1, description="Max output height in px")
    dpi: int = Field(150, ge=72, le=600, description="Output DPI")


class FontParams(BaseModel):
    fallback_font: str = Field("Noto Sans CJK SC", description="CJK fallback font")
    embed_fonts: bool = Field(True, description="Embed fonts in output")
    preserve_size: bool = Field(True, description="Preserve original font size")


class ConvertParams(BaseModel):
    ocr: OCRParams = Field(default_factory=OCRParams)
    layout: LayoutParams = Field(default_factory=LayoutParams)
    image: ImageParams = Field(default_factory=ImageParams)
    font: FontParams = Field(default_factory=FontParams)

    # Top-level shortcuts (match algo/models/params.py)
    output_format: str = Field("docx", description="Target format: docx/pptx/xlsx/html/jpg/png/markdown/txt")
    start_page: int = Field(0, ge=0, description="Start page (0-indexed)")
    end_page: Optional[int] = Field(None, ge=0, description="End page inclusive (None = last)")


class FormatInfo(BaseModel):
    """Metadata for a single supported conversion format (returned by ``GET /formats``)."""
    id: str = Field(..., description="Format identifier, e.g. 'docx'")
    name: str = Field(..., description="Human-readable name")
    icon: str = Field(..., description="Icon identifier (emoji or icon class)")
    description: str = Field(..., description="Short description of the format")
    target_ext: str = Field(..., description="Target file extension, e.g. '.docx'")
    mime_type: str = Field(..., description="Target MIME type")


# ── Request / Response schemas ───────────────────────────────────────────

class UploadResponse(BaseModel):
    """Response from ``POST /upload`` — the client uses ``file_id`` for the subsequent ``/convert`` call."""
    file_id: str
    filename: str
    size: int


class StartTaskRequest(BaseModel):
    """Request body for ``POST /tasks/{task_id}/start`` (restart an existing task).

    ``params`` is optional — if omitted, the task keeps its previously-stored
    params (only ``target_format`` is overridden).
    """
    target_format: str
    params: Optional[ConvertParams] = None


class StartConvertRequest(BaseModel):
    """One-shot conversion request: create + start a task.

    Used by both ``POST /convert`` (async, via Celery) and ``POST /convert/sync``
    (in-process). ``params`` always has a value (default factory), so handlers
    can treat it as non-None.
    """
    file_id: str
    target_format: str
    params: ConvertParams = Field(default_factory=ConvertParams)


class TaskResponse(BaseModel):
    """Response model for every task-related endpoint.

    ``result`` is consistent across endpoints (see ``app.api.convert._build_task_result``):

    - ``None`` while the task is queued / processing / failed, or has no result file.
    - ``{"file_id": <task id>, "filename": <result filename>, "path": <storage relative path>}``
      when ``status == "completed"``.

    Note: ``result.file_id`` is the **task** id (the handle ``/download/{id}``
    accepts), not the source File id. This is intentional.
    """
    id: str
    file_id: str
    target_format: str
    status: str
    progress: float
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FormatsResponse(BaseModel):
    """Response from ``GET /formats``."""
    formats: List[FormatInfo]


class ParamsResponse(BaseModel):
    """Response from ``GET /params/{format}`` — per-format default conversion params."""
    format: str
    default_params: ConvertParams
    description: Optional[str] = None


class ErrorResponse(BaseModel):
    """Standard error envelope (used by FastAPI's exception handlers)."""
    detail: str
    code: Optional[str] = None
