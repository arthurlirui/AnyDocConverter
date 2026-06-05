"""
PDF 重建器 — 从编辑后的 PDFDocument 重建 PDF 文件
"""

from __future__ import annotations

import io
import logging
import os
from typing import Optional

from algo.models.params import ConvertParams
from algo.models.pdf_document import PDFDocument, Page, TextBlock, ImageBlock
from algo.reconstruct.layout_renderer import LayoutRenderer
from algo.reconstruct.text_renderer import TextRenderer
from algo.reconstruct.image_processor import ImageProcessor

logger = logging.getLogger(__name__)


class PDFRebuilder:
    """从编辑后的 PDFDocument 重建 PDF 文件"""

    def __init__(self, params: Optional[ConvertParams] = None):
        self.params = params or ConvertParams()
        self.layout_renderer = LayoutRenderer(self.params)
        self.text_renderer = TextRenderer(self.params)
        self.image_processor = ImageProcessor(self.params)

    def rebuild(self, pdf_doc: PDFDocument, output_path: str):
        """将 PDFDocument 重建为 PDF 文件。

        Args:
            pdf_doc: 编辑后的 PDFDocument
            output_path: 输出 PDF 路径
        """
        import fitz

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        new_doc = fitz.open()

        for page in pdf_doc.pages:
            # 新建同样尺寸的页
            new_page = new_doc.new_page(
                width=page.width,
                height=page.height,
            )

            # 1. 插入图片
            for img_block in page.image_blocks:
                self.image_processor.insert_image(new_page, img_block)

            # 2. 插入文字块
            text_blocks = sorted(
                page.text_blocks, key=lambda tb: (tb.bbox[1], tb.bbox[0])
            )
            for tb in text_blocks:
                self.text_renderer.insert_text(new_page, tb)

            # 3. 布局后处理
            self.layout_renderer.post_process(new_page, page)

        new_doc.save(output_path, garbage=4, deflate=True, clean=True)
        new_doc.close()
        logger.info("PDF rebuilt: %s", output_path)
