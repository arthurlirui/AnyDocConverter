"""
PDFParser 主类 — 用 PyMuPDF 解析 PDF 文档
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import fitz  # PyMuPDF

from algo.models.params import ConvertParams
from algo.models.pdf_document import PDFDocument, Page
from algo.parser.text_extractor import extract_text_blocks
from algo.parser.image_extractor import extract_images
from algo.parser.layout_analyzer import LayoutAnalyzer
from algo.ocr.ocr_manager import OCRManager

logger = logging.getLogger(__name__)


class PDFParser:
    """PDF 解析器主类"""

    def __init__(self, params: Optional[ConvertParams] = None):
        self.params = params or ConvertParams()
        self.layout_analyzer = LayoutAnalyzer(self.params.layout)
        self.ocr_manager = OCRManager(self.params.ocr) if self.params.ocr.enabled else None

    def parse(self, file_path: str, params: Optional[ConvertParams] = None) -> PDFDocument:
        """解析 PDF 文件，返回 PDFDocument。

        Args:
            file_path: PDF 文件路径
            params: 可选的转换参数（覆盖初始化参数）

        Returns:
            PDFDocument 数据模型
        """
        if params is not None:
            self.params = params
            self.layout_analyzer = LayoutAnalyzer(self.params.layout)
            self.ocr_manager = (
                OCRManager(self.params.ocr) if self.params.ocr.enabled else None
            )

        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        doc = fitz.open(file_path)
        file_name = os.path.basename(file_path)
        total_pages = doc.page_count

        pages: list[Page] = []
        for i in range(total_pages):
            raw_page = doc[i]

            pdf_page = Page(
                page_num=i,
                width=raw_page.rect.width,
                height=raw_page.rect.height,
            )

            # 1. 提取文字块
            text_blocks = extract_text_blocks(raw_page, i)
            pdf_page.text_blocks = text_blocks

            # 2. 提取图片
            image_blocks = extract_images(raw_page, i)
            pdf_page.image_blocks = image_blocks

            # 3. 可选 OCR 增强
            if self.ocr_manager is not None:
                pdf_page = self.ocr_manager.enhance_page(pdf_page, raw_page)

            # 4. 版面分析（附加元数据，存入页对象属性）
            layout_info = self.layout_analyzer.analyze(pdf_page, raw_page)
            pdf_page._layout_info = layout_info  # type: ignore[attr-defined]

            pages.append(pdf_page)

            logger.debug(
                "Page %d: %d text blocks, %d image blocks",
                i, len(text_blocks), len(image_blocks),
            )

        doc.close()

        pdf_doc = PDFDocument(
            file_name=file_name,
            total_pages=total_pages,
            pages=pages,
        )

        return pdf_doc
