from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Conversion parameters (aligned with algo/models/params.py) ───────────

class OCRParams(BaseModel):
    enabled: bool = Field(False, description="Enable OCR enhancement")
    engine: str = Field("paddle", description="OCR engine: paddle / tesseract")
    language: str = Field("chi_sim", description="OCR language code")
    min_confidence: float = Field(0.5, ge=0.0, le=1.0, description="Min confidence threshold")


class LayoutParams(BaseModel):
    preservation: str = Field("exact", description="Layout preservation: exact / loose / adaptive")
    detect_tables: bool = Field(True, description="Detect tables")
    detect_images: bool = Field(True, description="Detect images")
    detect_headers_footers: bool = Field(True, description="Detect headers & footers")
    reading_order: bool = Field(True, description="Restore reading order")


class ImageParams(BaseModel):
    dpi: int = Field(300, ge=72, le=600, description="Output DPI")
    compression: str = Field("jpeg", description="Compression format: jpeg / png / webp")
    quality: int = Field(95, ge=1, le=100, description="JPEG/WebP quality")
    color_space: str = Field("rgb", description="Color space: rgb / grayscale / cmyk")


class FontParams(BaseModel):
    mode: str = Field("approximate", description="Font matching: exact / approximate / replace")
    fallback_font: str = Field("NotoSansCJK", description="Fallback font for CJK characters")
    embed_fonts: bool = Field(True, description="Embed fonts in output")
    subset_fonts: bool = Field(True, description="Subset embedded fonts")


class ConvertParams(BaseModel):
    ocr: OCRParams = Field(default_factory=OCRParams)
    layout: LayoutParams = Field(default_factory=LayoutParams)
    image: ImageParams = Field(default_factory=ImageParams)
    font: FontParams = Field(default_factory=FontParams)


class FormatInfo(BaseModel):
    id: str = Field(..., description="Format identifier, e.g. 'docx'")
    name: str = Field(..., description="Human-readable name")
    icon: str = Field(..., description="Icon identifier (emoji or icon class)")
    description: str = Field(..., description="Short description of the format")
    target_ext: str = Field(..., description="Target file extension, e.g. '.docx'")
    mime_type: str = Field(..., description="Target MIME type")


# ── Request / Response schemas ───────────────────────────────────────────

class UploadResponse(BaseModel):
    file_id: str
    filename: str
    size: int


class StartTaskRequest(BaseModel):
    target_format: str
    params: Optional[ConvertParams] = None


class StartConvertRequest(BaseModel):
    """One-shot conversion request: create + start a task."""
    file_id: str
    target_format: str
    params: ConvertParams = Field(default_factory=ConvertParams)


class TaskResponse(BaseModel):
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
    formats: List[FormatInfo]


class ParamsResponse(BaseModel):
    format: str
    default_params: ConvertParams
    description: Optional[str] = None


class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None
