"""
ConversionPipeline — 转换管线编排

统一入口 :func:`convert` 完成 PDF / 图片到目标格式的转换。编排流程：

    输入识别 → 选择转换器 → (转换器内部按需 OCR / 版式转换) → 返回结果路径

设计要点
--------
- 转换器为无状态的模块级函数（``to_*_converter.convert``），统一签名
  ``(file_path, params, output_dir) -> str``，便于在 pipeline 中以字典派发。
- 调用方传入的 ``params`` 不会被修改：内部使用 ``model_copy`` 创建副本并
  覆盖 ``output_format``。
- 当 ``output_dir`` 由本函数创建的临时目录时，异常退出会自动清理该目录，
  避免磁盘泄漏；成功路径交由调用方管理（典型场景：worker 读取结果后清理）。
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from typing import Optional

from algo.models.params import ConvertParams
from algo.ocr.ocr_text import is_image_file
from algo.converters import (
    convert_to_docx,
    convert_to_pptx,
    convert_to_xlsx,
    convert_to_html,
    convert_to_jpg,
    convert_to_png,
    convert_to_markdown,
    convert_to_txt,
)

logger = logging.getLogger(__name__)

# 格式到转换函数的映射。新增格式时：
#   1. 在 algo/converters/ 下实现 to_{format}_converter.convert；
#   2. 在 algo/converters/__init__.py 导出 convert_to_{format}；
#   3. 在此处注册一行；
#   4. 在 algo/utils.CONVERTER_FORMATS 中补上格式标识。
_FORMAT_MAP = {
    "docx": convert_to_docx,
    "pptx": convert_to_pptx,
    "xlsx": convert_to_xlsx,
    "html": convert_to_html,
    "jpg": convert_to_jpg,
    "png": convert_to_png,
    "markdown": convert_to_markdown,
    "txt": convert_to_txt,
}


def convert(
    file_path: str,
    target_format: str,
    params: Optional[ConvertParams] = None,
    output_dir: Optional[str] = None,
) -> str:
    """PDF / 图片转换管线入口。

    Args:
        file_path: 源 PDF 或图片文件路径。图片输入（png/jpg/…）会跳过
            PDF 预解析，直接路由到具备 OCR 能力的转换器。
        target_format: 目标格式标识符（不区分大小写，可带前导 ``.``），
            必须是 :data:`_FORMAT_MAP` 中已注册的格式。
        params: 转换参数；为 ``None`` 时使用 :class:`ConvertParams` 默认值。
            调用方传入的对象不会被修改。
        output_dir: 输出目录；为 ``None`` 时创建临时目录。异常退出时若该
            目录由本函数创建，会被自动清理。

    Returns:
        输出文件路径（单文件输出时）或输出目录路径（多文件输出时，
        例如多页 PDF 转 JPG/PNG）。

    Raises:
        FileNotFoundError: ``file_path`` 不存在。
        ValueError: ``target_format`` 不在支持列表中。
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

    output_dir_created_here = output_dir is None
    if output_dir_created_here:
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
        # 阶段 1: 输入识别。图片 / OCR-only 输入跳过 PDF 预解析。
        # 当前所有 converter 都会自行 fitz.open 处理 PDF，因此这里只做
        # 路径校验与日志，避免对 PDF 做一次无消费者的重复解析。
        if is_image_file(file_path):
            logger.info("Image input detected; routing to OCR-capable converter")
        else:
            logger.info("PDF input detected; delegating to %s converter", target_format)

        # 阶段 2: 调用具体转换器（转换器内部按需执行解析 / OCR / 版式转换）
        converter_fn = _FORMAT_MAP[target_format]
        output_path = converter_fn(file_path, params, output_dir)

        logger.info("Conversion complete: %s", output_path)
        return output_path
    except Exception:
        # 仅清理本函数创建的临时目录，避免误删调用方提供的目录。
        if output_dir_created_here and output_dir and os.path.isdir(output_dir):
            shutil.rmtree(output_dir, ignore_errors=True)
        raise


def get_supported_formats() -> list[str]:
    """获取支持的转换格式列表（委派到共享 utils）。"""
    from algo.utils import get_converter_formats
    return get_converter_formats()

