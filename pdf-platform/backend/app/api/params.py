from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.task import ConvertParams, ParamsResponse

router = APIRouter()


# Format-specific parameter defaults — every entry is structurally a
# ConvertParams (mirrors algo/models/params.py). Only fields that diverge
# from the global defaults need to appear here; everything else falls back
# to ConvertParams() defaults via model_validate(...).
_FORMAT_PARAMS: dict[str, dict] = {
    "docx": {
        "description": "Convert PDF to Microsoft Word document — fully editable",
        "default_params": {
            "image": {"dpi": 300, "quality": 95},
            "font": {"embed_fonts": True, "preserve_size": True},
        },
    },
    "xlsx": {
        "description": "Extract tables from PDF to Excel spreadsheet",
        "default_params": {
            "layout": {"detect_images": False, "detect_headers_footers": False},
            "image": {"dpi": 150, "quality": 85},
            "font": {"embed_fonts": False, "preserve_size": True},
        },
    },
    "pptx": {
        "description": "Convert PDF to PowerPoint presentation — editable slides",
        "default_params": {
            "layout": {"detect_headers_footers": False},
            "image": {"dpi": 300, "quality": 95},
            "font": {"embed_fonts": True, "preserve_size": True},
        },
    },
    "html": {
        "description": "Convert PDF to HTML web page with responsive layout",
        "default_params": {
            "image": {"dpi": 150, "quality": 85},
            "font": {"embed_fonts": False, "preserve_size": True},
        },
    },
    "markdown": {
        "description": "Convert PDF/images to editable Markdown. Enable OCR for scanned PDFs, photos, screenshots and non-standard images.",
        "default_params": {
            "layout": {"detect_images": False, "detect_tables": False},
            "ocr": {"enabled": False, "engine": "paddle", "language": "ch", "min_confidence": 0.45, "enhance_image": False, "enhance_mode": "standard", "upscale_factor": 1.0, "contrast": 1.15, "sharpness": 1.05, "binarize": False},
        },
    },
    "txt": {
        "description": "Extract editable plain text. Enable OCR for scanned PDFs, photos, screenshots and non-standard images.",
        "default_params": {
            "layout": {"detect_images": False, "detect_tables": False, "detect_headers_footers": False},
            "ocr": {"enabled": False, "engine": "paddle", "language": "ch", "min_confidence": 0.45, "enhance_image": False, "enhance_mode": "standard", "upscale_factor": 1.0, "contrast": 1.15, "sharpness": 1.05, "binarize": False},
        },
    },
    "jpg": {
        "description": "Render each PDF page as a high-quality JPEG image",
        "default_params": {
            "layout": {"detect_tables": False, "detect_headers_footers": False, "reading_order": False},
            "image": {"dpi": 300, "quality": 95},
        },
    },
    "png": {
        "description": "Render each PDF page as a lossless PNG image",
        "default_params": {
            "layout": {"detect_tables": False, "detect_headers_footers": False, "reading_order": False},
            "image": {"dpi": 300, "quality": 100},
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
    # Build a fully-populated ConvertParams: per-format overrides on top of
    # the schema's own defaults, so the response is always self-consistent.
    overrides = entry["default_params"]
    base = ConvertParams().model_dump()
    for section, values in overrides.items():
        base[section].update(values)
    base["output_format"] = format_id

    return ParamsResponse(
        format=format_id,
        default_params=ConvertParams(**base),
        description=entry["description"],
    )
