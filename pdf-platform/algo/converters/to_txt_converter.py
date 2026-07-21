"""
PDF → Plain Text 转换器
最简单的提取：用 PyMuPDF 按页提取文字 + 换页分隔。
"""

from __future__ import annotations

import logging
import os

import fitz

from algo.models.params import ConvertParams
from algo.ocr.ocr_text import is_image_file, ocr_image_to_text, ocr_pdf_to_text

logger = logging.getLogger(__name__)

PAGE_SEPARATOR = "\n\n--- Page {page_no} ---\n\n"


def convert(file_path: str, params: ConvertParams, output_dir: str) -> str:
    """PDF → TXT 转换。

    策略:
      - 用 PyMuPDF page.get_text("text") 提取纯文本
      - 页与页之间用分隔符隔开
      - 尊重 start_page/end_page 范围

    Returns:
        输出 .txt 文件路径
    """
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.txt")

    if is_image_file(file_path):
        content = ocr_image_to_text(file_path, params).strip() or "(No OCR text recognized)"
    elif params.ocr.enabled:
        content = ocr_pdf_to_text(file_path, params).strip() or "(No OCR text recognized)"
    else:
        doc = fitz.open(file_path)
        start = params.start_page
        end = params.end_page if params.end_page is not None else doc.page_count - 1
        # 限定 end 在合法范围内，避免越界 IndexError
        end = min(end, doc.page_count - 1)

        chunks: list[str] = []
        try:
            if start > end:
                raise ValueError(
                    f"Invalid page range: start_page={start} > end_page={end}"
                )
            for i in range(start, end + 1):
                page = doc[i]
                text = page.get_text("text").strip()
                if not text:
                    continue
                chunks.append(PAGE_SEPARATOR.format(page_no=i + 1) + text)
        finally:
            doc.close()

        content = "".join(chunks).strip() or "(No extractable text)"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
        f.write("\n")

    logger.info("Text conversion done: %s (%d chars)", output_path, len(content))
    return output_path
