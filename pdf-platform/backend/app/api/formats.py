"""``GET /formats`` — supported target format catalog.

Returns a static list of :class:`FormatInfo` for the frontend format picker.
The list is intentionally decoupled from :data:`algo.utils.CONVERTER_FORMATS`
so the UI can advertise formats that are *planned but not yet implemented*
(currently ``pdf-edit``). Selecting such a format will fail at the conversion
step with an "unsupported format" error from the pipeline — see the
"Known limitations" section of the top-level README.

When you add a real converter, add its :class:`FormatInfo` here **and**
register it in :data:`algo.pipeline._FORMAT_MAP`.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.schemas.task import FormatInfo, FormatsResponse

router = APIRouter()


# Known conversion formats — extensible; consumers can also fetch from algo.
# When the algo module is integrated, this can be replaced with a dynamic query.
# NOTE: `pdf-edit` is advertised to the UI but has NO converter implementation
# in algo/pipeline.py — selecting it produces a runtime ValueError. See README.
_KNOWN_FORMATS = [
    FormatInfo(
        id="docx",
        name="Word",
        icon="📄",
        description="Microsoft Word document (.docx)",
        target_ext=".docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
    FormatInfo(
        id="xlsx",
        name="Excel",
        icon="📊",
        description="Microsoft Excel spreadsheet (.xlsx)",
        target_ext=".xlsx",
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    FormatInfo(
        id="pptx",
        name="PowerPoint",
        icon="📽️",
        description="Microsoft PowerPoint presentation (.pptx)",
        target_ext=".pptx",
        mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ),
    FormatInfo(
        id="html",
        name="HTML",
        icon="🌐",
        description="Web page (.html)",
        target_ext=".html",
        mime_type="text/html",
    ),
    FormatInfo(
        id="markdown",
        name="Markdown",
        icon="📝",
        description="Editable Markdown text (.md), supports PaddleOCR for scanned PDFs/images",
        target_ext=".md",
        mime_type="text/markdown",
    ),
    FormatInfo(
        id="txt",
        name="Plain Text",
        icon="🔤",
        description="Editable plain text (.txt), supports PaddleOCR for scanned PDFs/images",
        target_ext=".txt",
        mime_type="text/plain",
    ),
    FormatInfo(
        id="png",
        name="PNG Image",
        icon="🖼️",
        description="PNG image per page (.png)",
        target_ext=".png",
        mime_type="image/png",
    ),
    FormatInfo(
        id="jpg",
        name="JPEG Image",
        icon="🖼️",
        description="JPEG image per page (.jpg)",
        target_ext=".jpg",
        mime_type="image/jpeg",
    ),
    FormatInfo(
        id="pdf-edit",
        name="PDF (Edit)",
        icon="📕",
        description="Editable PDF with metadata preservation (.pdf)",
        target_ext=".pdf",
        mime_type="application/pdf",
    ),
]


@router.get(
    "/formats",
    response_model=FormatsResponse,
    summary="List all supported conversion formats",
)
async def list_formats() -> FormatsResponse:
    """Return the list of supported target formats for conversion."""
    return FormatsResponse(formats=_KNOWN_FORMATS)
