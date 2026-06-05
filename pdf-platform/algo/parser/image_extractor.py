"""
图片提取器 — 利用 PyMuPDF 提取页面中的内嵌图片
"""

from __future__ import annotations

import io
import logging
from typing import Optional

from PIL import Image

from algo.models.pdf_document import ImageBlock

logger = logging.getLogger(__name__)


def extract_images(page, page_num: int, min_size: int = 256) -> list[ImageBlock]:
    """从 PyMuPDF Page 对象中提取内嵌图片。

    Args:
        page: PyMuPDF Page 对象
        page_num: 页码
        min_size: 最小图片字节数，低于此值的图片将被忽略

    Returns:
        ImageBlock 列表
    """
    blocks = []

    for img_info in page.get_images(full=True):
        xref = img_info[0]
        base_image = page.parent.extract_image(xref)

        if base_image is None:
            continue

        image_bytes = base_image.get("image")
        if image_bytes is None or len(image_bytes) < min_size:
            continue

        ext = base_image.get("ext", "png")

        # 尝试获取位置信息
        bbox = _get_image_bbox(page, xref)

        # 获取图片尺寸
        width = base_image.get("width")
        height = base_image.get("height")

        if bbox is None:
            # 无位置信息，用占位坐标
            bbox = (0, 0, width or 0, height or 0)

        ib = ImageBlock(
            image_data=image_bytes,
            bbox=bbox,
            dpi=None,  # PDF 内嵌图片通常无 DPI 元数据
            page_num=page_num,
            width=width,
            height=height,
            ext=ext,
        )
        blocks.append(ib)

    return blocks


def _get_image_bbox(page, xref: int) -> Optional[tuple[float, float, float, float]]:
    """尝试通过遍历页面显示列表获取图片的 bbox"""
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 1:  # 1 = image
            continue
        img = block.get("image", {})
        if isinstance(img, dict) and img.get("xref") == xref:
            return tuple(block.get("bbox"))
    return None


def image_bytes_to_pil(data: bytes) -> Optional[Image.Image]:
    """将图片字节转换为 PIL Image"""
    try:
        return Image.open(io.BytesIO(data))
    except Exception as e:
        logger.warning("Failed to convert image bytes to PIL: %s", e)
        return None


def pil_to_bytes(pil_img: Image.Image, fmt: str = "PNG", quality: int = 85) -> bytes:
    """将 PIL Image 转换为字节"""
    buf = io.BytesIO()
    pil_img.save(buf, format=fmt, quality=quality)
    return buf.getvalue()
