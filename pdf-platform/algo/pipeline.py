"""
ConversionPipeline — 转换管线编排

编排流程: 解析 → OCR增强 → 转换 → 后处理 → 返回结果路径
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from typing import Optional

from algo.models.params import ConvertParams
from algo.parser.pdf_parser import PDFParser
from algo.converters import (
    convert_to_docx,
    convert_to_pptx,
    convert_to_xlsx,
    convert_to_html,
    convert_to_jpg,
    convert_to_png,
)

logger = logging.getLogger(__name__)

# 格式到转换函数的映射
_FORMAT_MAP = {
    "docx": convert_to_docx,
    "pptx": convert_to_pptx,
    "xlsx": convert_to_xlsx,
    "html": convert_to_html,
    "jpg": convert_to_jpg,
    "png": convert_to_png,
}


def convert(
    file_path: str,
    target_format: str,
    params: Optional[ConvertParams] = None,
    output_dir: Optional[str] = None,
) -> str:
    """PDF 转换管线入口。

    Args:
        file_path: 源 PDF 文件路径
        target_format: 目标格式 (docx/pptx/xlsx/html/jpg)
        params: 转换参数（可选）
        output_dir: 输出目录（可选，默认使用临时目录）

    Returns:
        输出文件路径（单页时）或输出目录路径（多页时）

    Notes:
        当 output_dir 由本函数创建的临时目录时,异常退出会自动清理该目录。
        调用方传入的 params 不会被修改（内部使用 model_copy 创建副本）。

    Raises:
        FileNotFoundError: PDF 文件不存在
        ValueError: 不支持的目标格式
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    target_format = target_format.lower().lstrip(".")
    if target_format not in _FORMAT_MAP:
        raise ValueError(
            f"Unsupported format: {target_format}. "
            f"Supported: {', '.join(_FORMAT_MAP.keys())}"
        )

    if params is None:
        params = ConvertParams()

    # 避免修改调用方传入的可变对象（model_copy 创建 pydantic v2 副本）
    params = params.model_copy(update={"output_format": target_format})

    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="pdf_convert_")

    os.makedirs(output_dir, exist_ok=True)

    logger.info(
        "Starting conversion: %s → %s (pages %s-%s)",
        os.path.basename(file_path),
        target_format,
        params.start_page,
        params.end_page or "end",
    )

    try:
        # 阶段 1: 解析 PDF
        parser = PDFParser(params)
        pdf_doc = parser.parse(file_path)
        logger.info("Parsed: %d pages", pdf_doc.total_pages)

        # 阶段 2: 调用具体转换器（各转换器自行重新解析 PDF）
        converter_fn = _FORMAT_MAP[target_format]
        output_path = converter_fn(file_path, params, output_dir)

        logger.info("Conversion complete: %s", output_path)
        return output_path
    except Exception:
        # 异常时清理临时目录，避免磁盘泄漏
        if output_dir and os.path.isdir(output_dir):
            shutil.rmtree(output_dir, ignore_errors=True)
        raise


def get_supported_formats() -> list[str]:
    """获取支持的转换格式列表（委派到共享 utils）"""
    from algo.utils import get_converter_formats
    return get_converter_formats()
