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

    将 PDF 每一页渲染为无损 PNG，写入 ``output_dir``。

    - 单页：输出 ``{base_name}.png``，返回该文件路径。
    - 多页：第一页输出 ``{base_name}.png``，其余页输出
      ``{base_name}_page_{N:03d}.png``，并返回 ``output_dir`` 目录路径，
      以便调用方知道存在多个结果文件。

    页码处理说明：``params.start_page`` 为 0-indexed，而 pdf2image 的
    ``first_page``/``last_page`` 为 1-indexed，故需 +1 转换。

    Args:
        file_path: 源 PDF 文件路径
        params: 转换参数（使用 image.dpi / start_page / end_page）
        output_dir: 输出目录（不存在会自动创建）

    Returns:
        单页时为输出文件路径；多页时为输出目录路径。
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

    if not pages:
        raise RuntimeError("pdf2image returned no pages for input: %s" % file_path)

    # 第一页命名为 {base_name}.png，与单页输出保持一致
    output_path = os.path.join(output_dir, f"{base_name}.png")
    pages[0].save(output_path, "PNG")

    # 其余页使用 _page_{N:03d} 命名，N 为 PDF 内绝对页码
    for idx, page_img in enumerate(pages[1:], start=2):
        page_num = params.start_page + idx
        filename = f"{base_name}_page_{page_num:03d}.png"
        page_path = os.path.join(output_dir, filename)
        page_img.save(page_path, "PNG")

    logger.info("PNG conversion done: %d pages -> %s", len(pages), output_dir)
    # 多页时返回目录，让调用方知道存在多份结果
    return output_dir if len(pages) > 1 else output_path
