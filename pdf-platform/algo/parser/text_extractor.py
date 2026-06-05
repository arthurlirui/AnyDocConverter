"""
文字块提取器 — 利用 PyMuPDF 提取每页的文字信息
"""

from __future__ import annotations

import logging
from typing import Optional

from algo.models.pdf_document import TextBlock

logger = logging.getLogger(__name__)


def extract_text_blocks(page, page_num: int) -> list[TextBlock]:
    """从 PyMuPDF Page 对象中提取所有文字块。

    返回 TextBlock 列表，已按阅读顺序排序。
    """
    blocks = []

    # 使用 PyMuPDF 的 get_text("dict") 获取结构化信息
    text_dict = page.get_text("dict")

    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:  # 0=text, 1=image
            continue

        bbox_raw = block.get("bbox", (0, 0, 0, 0))
        bbox = _normalize_bbox(bbox_raw)

        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "").strip()
                if not text:
                    continue

                font_name = span.get("font", None)
                font_size = span.get("size", None)
                color_raw = span.get("color", None)

                tb = TextBlock(
                    text=text,
                    font_name=font_name,
                    font_size=font_size,
                    bold=_check_bold(span),
                    italic=_check_italic(span),
                    color=_color_to_hex(color_raw),
                    bbox=_normalize_bbox(span.get("bbox", bbox_raw)),
                    page_num=page_num,
                )
                blocks.append(tb)

    return blocks


def extract_raw_text(page) -> str:
    """提取页面的纯文本（快速模式）"""
    return page.get_text("text")


def _normalize_bbox(bbox: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    """确保 bbox 坐标合法"""
    x0, y0, x1, y1 = bbox
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def _check_bold(span: dict) -> bool:
    """根据字体名称或 flags 判断是否加粗"""
    font = (span.get("font") or "").lower()
    if "bold" in font or "heavy" in font:
        return True
    flags = span.get("flags", 0)
    return bool(flags & 2)  # PyMuPDF: bit 1 = bold


def _check_italic(span: dict) -> bool:
    """根据字体名称或 flags 判断是否斜体"""
    font = (span.get("font") or "").lower()
    if "italic" in font or "oblique" in font:
        return True
    flags = span.get("flags", 0)
    return bool(flags & 1)  # PyMuPDF: bit 0 = italic


def _color_to_hex(color_raw) -> Optional[str]:
    """将 PyMuPDF 颜色值转为十六进制字符串 (#RRGGBB)"""
    if color_raw is None:
        return None
    if isinstance(color_raw, (int, float)):
        # PyMuPDF uses int color values
        color_raw = int(color_raw)
        r = (color_raw >> 16) & 0xFF
        g = (color_raw >> 8) & 0xFF
        b = color_raw & 0xFF
        return f"#{r:02x}{g:02x}{b:02x}"
    if isinstance(color_raw, (list, tuple)) and len(color_raw) >= 3:
        r = int(color_raw[0] * 255)
        g = int(color_raw[1] * 255)
        b = int(color_raw[2] * 255)
        return f"#{r:02x}{g:02x}{b:02x}"
    return None
