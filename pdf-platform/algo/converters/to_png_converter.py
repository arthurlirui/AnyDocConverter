"""
PDF → PNG 转换器
使用 pdf2image (Poppler) 每页转 PNG
"""

from __future__ import annotations

import logging
import os

from algo.models.params import ConvertParams

logger = logging.getLogger(__name__)


def convert(file_path: str, params: ConvertParams, output_dir: str) -> str:
    """PDF → PNG 转换

    将每一页转换为独立的 PNG 图片文件。
    如果只有一页，直接输出 single.png；
    如果多页，输出 {basename}_page_001.png 等。

    Returns:
        单页: 输出文件路径
        多页: 输出目录路径
    """
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(file_path))[0]

    try:
        from pdf2image import convert_from_path
    except ImportError:
        logger.error("pdf2image not installed. pip install pdf2image")
        raise

    pages = convert_from_path(
        file_path,
        dpi=params.image.dpi,
        first_page=params.start_page + 1,
        last_page=(
            params.end_page + 1 if params.end_page is not None else None
        ),
        fmt="png",
    )

    if len(pages) == 1:
        output_path = os.path.join(output_dir, f"{base_name}.png")
        pages[0].save(output_path, "PNG")
        logger.info("PNG conversion done: %s", output_path)
        return output_path

    # 多页
    for idx, page_img in enumerate(pages):
        page_num = params.start_page + idx + 1
        filename = f"{base_name}_page_{page_num:03d}.png"
        page_path = os.path.join(output_dir, filename)
        page_img.save(page_path, "PNG")

    logger.info("PNG conversion done: %d pages -> %s", len(pages), output_dir)
    return output_dir
