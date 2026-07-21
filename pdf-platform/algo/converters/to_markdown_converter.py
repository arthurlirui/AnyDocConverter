"""
PDF / 图片 → Markdown 转换器。

策略：
- 图片输入或开启 OCR：调用 :mod:`algo.ocr.ocr_text` 提取纯文本，
  直接作为 Markdown 内容（OCR 结果已分行）。
- 普通文本 PDF：用 PyMuPDF 提取文字结构，根据首段 span 的字号推断
  标题层级（≥20 → H1，≥16 → H2，≥14 → H3，其余为正文），输出格式化
  Markdown，页与页之间用空行分隔。
"""

from __future__ import annotations

import logging
import os

import fitz

from algo.models.params import ConvertParams
from algo.ocr.ocr_text import is_image_file, ocr_image_to_text, ocr_pdf_to_text

logger = logging.getLogger(__name__)

# 字号 → Markdown 标题级别阈值（pt）
_HEADING_THRESHOLDS = (
    (20, "# "),
    (16, "## "),
    (14, "### "),
)


def convert(file_path: str, params: ConvertParams, output_dir: str) -> str:
    """PDF / 图片 → Markdown 转换。

    Args:
        file_path: 源 PDF 或图片路径。
        params: 转换参数（使用 ocr / start_page / end_page）。
        output_dir: 输出目录（不存在会自动创建）。

    Returns:
        输出 .md 文件路径。
    """
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.md")

    if is_image_file(file_path):
        text = ocr_image_to_text(file_path, params).strip()
        md_content = text if text else "(No OCR text recognized)"
    elif params.ocr.enabled:
        text = ocr_pdf_to_text(file_path, params).strip()
        md_content = text if text else "(No OCR text recognized)"
    else:
        doc = fitz.open(file_path)
        start = params.start_page
        end = params.end_page if params.end_page is not None else doc.page_count - 1
        # 限定 end 在合法范围内，避免越界 IndexError
        end = min(end, doc.page_count - 1)

        md_lines: list[str] = []

        try:
            if start > end:
                raise ValueError(
                    f"Invalid page range: start_page={start} > end_page={end}"
                )
            for i in range(start, end + 1):
                page = doc[i]
                blocks = page.get_text("dict").get("blocks", [])

                page_md: list[str] = []
                for block in blocks:
                    if block.get("type") != 0:  # 跳过图片块
                        continue
                    for line in block.get("lines", []):
                        line_text = "".join(
                            span.get("text", "") for span in line.get("spans", [])
                        ).strip()
                        if not line_text:
                            continue

                        # 根据字体大小推断标题级别
                        first_span = line["spans"][0] if line["spans"] else None
                        font_size = first_span.get("size", 12) if first_span else 12

                        prefix = ""
                        for threshold, heading in _HEADING_THRESHOLDS:
                            if font_size >= threshold:
                                prefix = heading
                                break
                        page_md.append(f"{prefix}{line_text}" if prefix else line_text)

                if page_md:
                    if md_lines:
                        md_lines.append("")  # 页间空行
                    md_lines.extend(page_md)
        finally:
            doc.close()

        md_content = "\n\n".join(md_lines) if md_lines else "(No extractable text)"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    logger.info("Markdown conversion done: %s", output_path)
    return output_path

