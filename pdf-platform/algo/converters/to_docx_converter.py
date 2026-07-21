"""
PDF / 图片 → DOCX 转换器。

两条转换路径：

1. **OCR 模式**（``params.ocr.enabled`` 或图片输入）：
   调用 :mod:`algo.ocr.ocr_text` 提取纯文本，写入可编辑的 DOCX 段落。
   适用于扫描版 PDF、照片、截图等无文本层的输入。

2. **版式还原模式**（默认）：
   使用 ``pdf2docx`` 做基础转换以保留版式，再用 ``python-docx``
   做后处理（设置中文字体回退）。
"""

from __future__ import annotations

import logging
import os
import tempfile
from typing import Optional

from algo.models.params import ConvertParams
from algo.models.pdf_document import PDFDocument, Page
from algo.ocr.ocr_text import is_image_file, ocr_image_to_text, ocr_pdf_to_text

logger = logging.getLogger(__name__)


def convert(file_path: str, params: ConvertParams, output_dir: str) -> str:
    """PDF / 图片 → DOCX 转换。

    根据输入类型与 ``params.ocr.enabled`` 选择 OCR 文本路径或 pdf2docx
    版式还原路径，输出 ``{base_name}.docx`` 到 ``output_dir``。

    Args:
        file_path: 源 PDF 或图片路径。
        params: 转换参数（使用 ocr / font / start_page / end_page）。
        output_dir: 输出目录（不存在会自动创建）。

    Returns:
        输出 .docx 文件路径。
    """
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.docx")

    # OCR 模式：面向扫描 PDF / 照片 / 非标准图片，输出真正可编辑文本。
    # 非 OCR 模式：保留 pdf2docx 的版式还原能力。
    if is_image_file(file_path) or params.ocr.enabled:
        _convert_ocr_text_to_docx(file_path, output_path, params)
    else:
        # 阶段 1: 基础转换
        _convert_via_pdf2docx(file_path, output_path, params)

        # 阶段 2: 后处理
        _postprocess_with_python_docx(output_path, params)

    logger.info("DOCX conversion done: %s", output_path)
    return output_path


def _convert_ocr_text_to_docx(file_path: str, docx_path: str, params: ConvertParams):
    """Use OCR result as editable DOCX paragraphs.

    OCR 结果按行拆分为段落写入 DOCX；识别为空时写入占位段落，
    避免生成完全空白文档。
    """
    try:
        from docx import Document
    except ImportError:
        logger.error("python-docx not installed. pip install python-docx")
        raise

    if is_image_file(file_path):
        text = ocr_image_to_text(file_path, params)
    else:
        text = ocr_pdf_to_text(file_path, params)

    doc = Document()
    doc.add_heading("OCR Result", level=1)
    if text.strip():
        for para in text.split("\n"):
            if para.strip():
                doc.add_paragraph(para.strip())
    else:
        doc.add_paragraph("(No OCR text recognized)")
    doc.save(docx_path)
    _postprocess_with_python_docx(docx_path, params)


def _convert_via_pdf2docx(pdf_path: str, docx_path: str, params: ConvertParams):
    """使用 pdf2docx 库执行基础转换。

    ``pdf2docx`` 的 ``start``/``end`` 为 0-indexed 半开区间，
    与 :class:`ConvertParams` 的 ``start_page`` / ``end_page``（含端点）一致，
    直接透传即可。
    """
    try:
        from pdf2docx import Converter

        cv = Converter(pdf_path)
        cv.convert(
            docx_path,
            start=params.start_page,
            end=params.end_page,
        )
        cv.close()
    except ImportError:
        logger.error("pdf2docx not installed. pip install pdf2docx")
        raise
    except Exception as e:
        logger.error("pdf2docx conversion failed: %s", e)
        raise


def _postprocess_with_python_docx(docx_path: str, params: ConvertParams):
    """用 python-docx 进行后处理。

    遍历所有 run，对未指定字体或字体名含 ``CJK`` 的 run 设置
    ``params.font.fallback_font``，解决部分环境下中文显示为方块的问题。
    """
    try:
        from docx import Document
        from docx.shared import Pt
    except ImportError:
        logger.warning("python-docx not installed, skipping post-processing")
        return

    if not os.path.isfile(docx_path):
        logger.warning("DOCX file not found for post-processing: %s", docx_path)
        return

    try:
        doc = Document(docx_path)

        # 遍历段落，设置回退中文字体
        fallback = params.font.fallback_font
        for paragraph in doc.paragraphs:
            for run in paragraph.runs:
                if run.font.name is None or "CJK" in str(run.font.name):
                    run.font.name = fallback

        doc.save(docx_path)
    except Exception as e:
        logger.warning("DOCX post-processing failed: %s", e)

