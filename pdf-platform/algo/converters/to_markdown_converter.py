"""
PDF → Markdown 转换器
使用 PyMuPDF 提取文字结构，输出格式化 Markdown
"""

from __future__ import annotations

import logging
import os

import fitz

from algo.models.params import ConvertParams

logger = logging.getLogger(__name__)


def convert(file_path: str, params: ConvertParams, output_dir: str) -> str:
    """PDF → Markdown 转换

    策略:
    1. 逐页提取文字
    2. 根据字体大小推断标题层级
    3. 输出格式化 Markdown

    Returns:
        输出 .md 文件路径
    """
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.md")

    doc = fitz.open(file_path)
    start = params.start_page
    end = params.end_page if params.end_page is not None else doc.page_count - 1

    md_lines: list[str] = []

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

                if font_size >= 20:
                    page_md.append(f"# {line_text}")
                elif font_size >= 16:
                    page_md.append(f"## {line_text}")
                elif font_size >= 14:
                    page_md.append(f"### {line_text}")
                else:
                    page_md.append(line_text)

        if page_md:
            if md_lines:
                md_lines.append("")  # 页间空行
            md_lines.extend(page_md)

    doc.close()

    md_content = "\n\n".join(md_lines) if md_lines else "(No extractable text)"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    logger.info("Markdown conversion done: %s", output_path)
    return output_path
