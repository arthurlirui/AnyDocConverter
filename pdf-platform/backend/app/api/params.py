from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.task import (
    ConvertParams,
    OCRParams,
    LayoutParams,
    ImageParams,
    FontParams,
    ParamsResponse,
)

router = APIRouter()

# Format-specific parameter defaults (aligned with algo/models/params.py)
_FORMAT_PARAMS: dict[str, dict] = {
    "docx": {
        "description": "Convert PDF to Microsoft Word document — fully editable",
        "default_params": {
            "ocr": {"enabled": False, "engine": "paddle", "language": "chi_sim", "min_confidence": 0.5},
            "layout": {"preservation": "exact", "detect_tables": True, "detect_images": True, "detect_headers_footers": True, "reading_order": True},
            "image": {"dpi": 300, "compression": "jpeg", "quality": 95, "color_space": "rgb"},
            "font": {"mode": "approximate", "fallback_font": "NotoSansCJK", "embed_fonts": True, "subset_fonts": True},
        },
    },
    "xlsx": {
        "description": "Extract tables from PDF to Excel spreadsheet",
        "default_params": {
            "ocr": {"enabled": False, "engine": "paddle", "language": "chi_sim", "min_confidence": 0.5},
            "layout": {"preservation": "exact", "detect_tables": True, "detect_images": False, "detect_headers_footers": False, "reading_order": True},
            "image": {"dpi": 150, "compression": "jpeg", "quality": 85, "color_space": "rgb"},
            "font": {"mode": "approximate", "fallback_font": "NotoSansCJK", "embed_fonts": False, "subset_fonts": False},
        },
    },
    "pptx": {
        "description": "Convert PDF to PowerPoint presentation — editable slides",
        "default_params": {
            "ocr": {"enabled": False, "engine": "paddle", "language": "chi_sim", "min_confidence": 0.5},
            "layout": {"preservation": "exact", "detect_tables": True, "detect_images": True, "detect_headers_footers": False, "reading_order": True},
            "image": {"dpi": 300, "compression": "jpeg", "quality": 95, "color_space": "rgb"},
            "font": {"mode": "approximate", "fallback_font": "NotoSansCJK", "embed_fonts": True, "subset_fonts": True},
        },
    },
    "html": {
        "description": "Convert PDF to HTML web page with responsive layout",
        "default_params": {
            "ocr": {"enabled": False, "engine": "paddle", "language": "chi_sim", "min_confidence": 0.5},
            "layout": {"preservation": "adaptive", "detect_tables": True, "detect_images": True, "detect_headers_footers": True, "reading_order": True},
            "image": {"dpi": 150, "compression": "jpeg", "quality": 85, "color_space": "rgb"},
            "font": {"mode": "approximate", "fallback_font": "NotoSansCJK", "embed_fonts": False, "subset_fonts": False},
        },
    },
    "jpg": {
        "description": "Render each PDF page as a high-quality JPEG image",
        "default_params": {
            "ocr": {"enabled": False, "engine": "paddle", "language": "chi_sim", "min_confidence": 0.5},
            "layout": {"preservation": "exact", "detect_tables": False, "detect_images": True, "detect_headers_footers": False, "reading_order": False},
            "image": {"dpi": 300, "compression": "jpeg", "quality": 95, "color_space": "rgb"},
            "font": {"mode": "approximate", "fallback_font": "NotoSansCJK", "embed_fonts": False, "subset_fonts": False},
        },
    },
}


@router.get(
    "/params/{format_id}",
    response_model=ParamsResponse,
    summary="Get default conversion parameters for a format",
)
async def get_format_params(format_id: str) -> ParamsResponse:
    """Return the default conversion parameters for the specified format."""
    if format_id not in _FORMAT_PARAMS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown format: {format_id}",
        )

    entry = _FORMAT_PARAMS[format_id]
    return ParamsResponse(
        format=format_id,
        default_params=ConvertParams(**entry["default_params"]),
        description=entry["description"],
    )
