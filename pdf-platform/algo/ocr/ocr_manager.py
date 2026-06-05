"""
OCR 引擎调度管理器
"""

from __future__ import annotations

import io
import logging
from typing import Optional

from PIL import Image

from algo.models.params import OCRParams
from algo.models.pdf_document import Page, TextBlock
from algo.ocr.paddle_ocr_adapter import PaddleOCRAdapter
from algo.ocr.tesseract_ocr_adapter import TesseractOCRAdapter

logger = logging.getLogger(__name__)


class OCRManager:
    """OCR 引擎调度 — 根据配置选择 PaddleOCR 或 Tesseract"""

    def __init__(self, params: OCRParams):
        self.params = params
        self._adapter = self._create_adapter()

    def _create_adapter(self):
        if self.params.engine == "paddle":
            return PaddleOCRAdapter(self.params)
        elif self.params.engine == "tesseract":
            return TesseractOCRAdapter(self.params)
        else:
            raise ValueError(f"Unsupported OCR engine: {self.params.engine}")

    def enhance_page(self, page: Page, raw_page=None) -> Page:
        """对页面进行 OCR 增强：在已有文字块基础上，补充检测到的文字。

        Args:
            page: Page 数据模型
            raw_page: PyMuPDF Page 对象（可选，用于渲染图片）

        Returns:
            增强后的 Page
        """
        # 如果没有文字块或文字块极少，尝试 OCR 全页
        total_chars = sum(len(tb.text) for tb in page.text_blocks)

        if total_chars > 10:
            # 已有足够文字，跳过 OCR 增强
            return page

        # 从 raw_page 渲染图片做 OCR
        if raw_page is None:
            logger.warning("No raw_page provided for OCR, skipping")
            return page

        try:
            # 渲染页面为 PIL Image
            pix = raw_page.get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
        except Exception as e:
            logger.warning("Failed to render page for OCR: %s", e)
            return page

        ocr_results = self._adapter.recognize(img)

        for result in ocr_results:
            text = result.get("text", "").strip()
            if not text:
                continue
            confidence = result.get("confidence", 0)
            if confidence < self.params.min_confidence:
                continue

            bbox = result.get("bbox", (0, 0, 0, 0))
            tb = TextBlock(
                text=text,
                font_name=None,
                font_size=None,
                bold=False,
                italic=False,
                color=None,
                bbox=bbox,
                page_num=page.page_num,
            )
            page.text_blocks.append(tb)

        return page
