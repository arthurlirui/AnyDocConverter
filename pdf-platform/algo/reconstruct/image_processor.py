"""
图片处理器 — 在 PDF 重建时处理图片的插入与缩放
"""

from __future__ import annotations

import io
import logging
from typing import Optional

from PIL import Image

from algo.models.params import ConvertParams
from algo.models.pdf_document import ImageBlock

logger = logging.getLogger(__name__)


class ImageProcessor:
    """图片处理 — 缩放、格式转换、插入 PDF"""

    def __init__(self, params: ConvertParams):
        self.params = params

    def insert_image(self, page, img_block: ImageBlock):
        """在 PyMuPDF Page 上插入图片块。

        Args:
            page: PyMuPDF Page 对象
            img_block: ImageBlock 数据模型
        """
        # 图片数据预处理：缩放
        image_data = self._resize_if_needed(img_block)

        # 插入图片
        rect = img_block.bbox
        try:
            page.insert_image(
                rect,
                stream=image_data,
            )
        except Exception as e:
            logger.warning("Failed to insert image on page %d: %s",
                           img_block.page_num, e)

    def _resize_if_needed(self, img_block: ImageBlock) -> bytes:
        """根据参数缩放图片（如最大宽度/高度限制）"""
        max_w = self.params.image.max_width
        max_h = self.params.image.max_height

        if max_w is None and max_h is None:
            return img_block.image_data

        try:
            pil_img = Image.open(io.BytesIO(img_block.image_data))
            orig_w, orig_h = pil_img.size

            new_w, new_h = orig_w, orig_h
            if max_w is not None and orig_w > max_w:
                ratio = max_w / orig_w
                new_w = max_w
                new_h = int(orig_h * ratio)
            if max_h is not None and new_h > max_h:
                ratio = max_h / new_h
                new_h = max_h
                new_w = int(new_w * ratio)

            if (new_w, new_h) != (orig_w, orig_h):
                pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)

                buf = io.BytesIO()
                pil_img.save(buf, format=img_block.ext.upper())
                return buf.getvalue()
        except Exception as e:
            logger.warning("Image resize failed: %s", e)

        return img_block.image_data
