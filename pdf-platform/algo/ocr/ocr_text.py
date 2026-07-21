"""Shared OCR-to-text helpers for PDFs and images.

This module wraps :class:`~algo.ocr.ocr_manager.OCRManager` with two
convenience entry points used by text-oriented converters (txt / markdown /
docx / html):

- :func:`ocr_image_to_text` — OCR a single image file into plain text.
- :func:`ocr_pdf_to_text`   — OCR a page range of a PDF into plain text,
                              respecting ``start_page`` / ``end_page`` / ``dpi``.

It also exposes :func:`is_image_file` (used by the pipeline to route image
inputs away from PDF parsing) and two helpers (:func:`sort_ocr_lines`,
:func:`results_to_text`) that turn raw OCR boxes into readable plain text
with simple line grouping by Y-coordinate.
"""

from __future__ import annotations

import io
import logging
import os
from pathlib import Path
from typing import Iterable

import fitz
from PIL import Image, ImageOps

from algo.models.params import ConvertParams, OCRParams
from algo.ocr.ocr_manager import OCRManager

logger = logging.getLogger(__name__)

# 视为图片输入的扩展名集合。命中即跳过 PDF 预解析。
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def is_image_file(file_path: str | os.PathLike[str]) -> bool:
    """Return True if ``file_path`` has a known raster image extension."""
    return Path(file_path).suffix.lower() in IMAGE_EXTS


def sort_ocr_lines(results: list[dict], y_tolerance: float = 12.0) -> list[dict]:
    """Sort OCR boxes by reading order: top-to-bottom, then left-to-right.

    Y 坐标按 ``y_tolerance`` 分桶后排序，使同一行内的多个 box 落在同一桶，
    再在桶内按 X 排序，得到近似的阅读顺序。
    """
    if not results:
        return []
    return sorted(results, key=lambda r: (round(float(r["bbox"][1]) / y_tolerance), float(r["bbox"][0])))


def results_to_text(results: list[dict], min_confidence: float = 0.0) -> str:
    """Convert OCR boxes to plain text with simple line grouping.

    过滤掉低于 ``min_confidence`` 的结果后，按 Y 坐标分行（同行的 box
    间距 <= 14px 视为同一行），行内按 X 升序拼接，行间用 ``\\n`` 分隔。
    """
    lines = sort_ocr_lines([
        r for r in results
        if r.get("text") and float(r.get("confidence", 0.0)) >= min_confidence
    ])
    if not lines:
        return ""

    grouped: list[list[dict]] = []
    for item in lines:
        y0 = float(item["bbox"][1])
        if not grouped:
            grouped.append([item])
            continue
        prev_y = sum(float(x["bbox"][1]) for x in grouped[-1]) / len(grouped[-1])
        if abs(y0 - prev_y) <= 14:
            grouped[-1].append(item)
        else:
            grouped.append([item])

    text_lines: list[str] = []
    for group in grouped:
        group = sorted(group, key=lambda r: float(r["bbox"][0]))
        text_lines.append(" ".join(str(r["text"]).strip() for r in group if str(r["text"]).strip()))
    return "\n".join(line for line in text_lines if line.strip())


def _render_pdf_page(page, dpi: int) -> Image.Image:
    """Render a PyMuPDF page to a PIL Image at the given DPI."""
    pix = page.get_pixmap(dpi=dpi)
    return Image.open(io.BytesIO(pix.tobytes("png")))


def ocr_image_to_text(file_path: str, params: ConvertParams | OCRParams) -> str:
    """OCR an image file into editable plain text.

    ``params`` 可以是完整的 :class:`ConvertParams`（取其 ``ocr`` 子配置）
    或单独的 :class:`OCRParams`。无论原配置是否启用 OCR，本函数都会强制
    启用（调用方已明确要做 OCR）。
    """
    ocr_params = params if isinstance(params, OCRParams) else params.ocr
    if not ocr_params.enabled:
        ocr_params = ocr_params.model_copy(update={"enabled": True})
    manager = OCRManager(ocr_params)
    # exif_transpose 修正手机拍照的方向旋转，避免横躺的文字
    img = ImageOps.exif_transpose(Image.open(file_path))
    results = manager.recognize_image(img)
    return results_to_text(results, ocr_params.min_confidence)


def ocr_pdf_to_text(file_path: str, params: ConvertParams) -> str:
    """OCR a PDF page range into editable plain text.

    遍历 ``params.start_page`` 到 ``params.end_page``（含），逐页渲染为
    图片后送入 OCR。每页结果以 ``--- Page N OCR ---`` 分隔。空页面会被
    跳过；``start_page > end_page`` 时返回空串并打印告警。
    """
    ocr_params = params.ocr.model_copy(update={"enabled": True})
    manager = OCRManager(ocr_params)
    doc = fitz.open(file_path)
    start = params.start_page
    end = params.end_page if params.end_page is not None else doc.page_count - 1
    end = min(end, doc.page_count - 1)
    dpi = params.image.dpi or 200

    chunks: list[str] = []
    try:
        if start > end:
            logger.warning(
                "ocr_pdf_to_text: empty page range start=%d end=%d", start, end
            )
            return ""
        for i in range(start, end + 1):
            page = doc[i]
            img = _render_pdf_page(page, dpi=dpi)
            results = manager.recognize_image(img)
            text = results_to_text(results, ocr_params.min_confidence)
            if text.strip():
                chunks.append(f"\n\n--- Page {i + 1} OCR ---\n\n{text.strip()}")
    finally:
        doc.close()
    return "".join(chunks).strip()
