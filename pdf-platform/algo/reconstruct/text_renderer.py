"""
文字渲染器 — 在 PDF 中插入文字块
"""

from __future__ import annotations

import logging
from typing import Optional

from algo.models.params import ConvertParams
from algo.models.pdf_document import TextBlock

logger = logging.getLogger(__name__)


class TextRenderer:
    """文字渲染 — 在 PyMuPDF Page 上插入 TextBlock"""

    def __init__(self, params: ConvertParams):
        self.params = params

    def insert_text(self, page, tb: TextBlock):
        """在 PyMuPDF Page 上插入文字块。

        使用 PyMuPDF 的 insert_text 方法，保留字体、颜色、大小等信息。
        """
        point = (tb.bbox[0], tb.bbox[1])

        # 构建字体参数
        fontname = tb.font_name or self.params.font.fallback_font
        fontsize = tb.font_size or 12

        # 颜色处理
        color = (0, 0, 0)  # 默认黑色
        if tb.color:
            try:
                hex_color = tb.color.lstrip("#")
                r = int(hex_color[0:2], 16) / 255.0
                g = int(hex_color[2:4], 16) / 255.0
                b = int(hex_color[4:6], 16) / 255.0
                color = (r, g, b)
            except (ValueError, IndexError):
                pass

        try:
            page.insert_text(
                point,
                tb.text,
                fontname=fontname,
                fontsize=fontsize,
                color=color,
            )
        except Exception as e:
            logger.warning(
                "Failed to insert text '%s' with font '%s': %s",
                tb.text[:20],
                fontname,
                e,
            )
            # 尝试用默认字体回退
            try:
                page.insert_text(
                    point,
                    tb.text,
                    fontsize=fontsize,
                    color=color,
                )
            except Exception as e2:
                logger.error(
                    "Fallback insert also failed: %s", e2
                )
