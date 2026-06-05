"""
PDF → DOCX 转换器
使用 pdf2docx 做基础转换 + python-docx 后处理
"""

from __future__ import annotations

import logging
import os
import tempfile
from typing import Optional

from algo.models.params import ConvertParams
from algo.models.pdf_document import PDFDocument, Page

logger = logging.getLogger(__name__)


def convert(file_path: str, params: ConvertParams, output_dir: str) -> str:
    """PDF → DOCX 转换

    使用 pdf2docx 做基础转换，然后通过 python-docx 后处理
    （调整字体、图片等）。

    Returns:
        输出 .docx 文件路径
    """
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.docx")

    # 阶段 1: 基础转换
    _convert_via_pdf2docx(file_path, output_path, params)

    # 阶段 2: 后处理
    _postprocess_with_python_docx(output_path, params)

    logger.info("DOCX conversion done: %s", output_path)
    return output_path


def _convert_via_pdf2docx(pdf_path: str, docx_path: str, params: ConvertParams):
    """使用 pdf2docx 库执行基础转换"""
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
    """用 python-docx 进行后处理"""
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
