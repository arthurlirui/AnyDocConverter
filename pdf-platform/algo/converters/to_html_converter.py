"""
PDF → HTML 转换器
文字 + 图片 → HTML + CSS
"""

from __future__ import annotations

import base64
import io
import logging
import os
from typing import Optional

import fitz  # PyMuPDF
from PIL import Image

from algo.models.params import ConvertParams

logger = logging.getLogger(__name__)


def convert(file_path: str, params: ConvertParams, output_dir: str) -> str:
    """PDF → HTML 转换

    策略:
    1. 每页渲染为 div，绝对定位文字和图片
    2. 图片内嵌为 base64 data URI
    3. 生成自适应 HTML

    Returns:
        输出 .html 文件路径
    """
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.html")

    doc = fitz.open(file_path)
    start = params.start_page
    end = params.end_page if params.end_page is not None else doc.page_count - 1

    html_parts = [
        "<!DOCTYPE html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f"<title>{base_name}</title>",
        "<style>",
        "* { margin: 0; padding: 0; box-sizing: border-box; }",
        "body { background: #e0e0e0; font-family: 'Noto Sans CJK SC', sans-serif; }",
        ".page {",
        "  position: relative;",
        "  background: white;",
        "  margin: 20px auto;",
        "  box-shadow: 0 2px 8px rgba(0,0,0,0.15);",
        "  overflow: hidden;",
        "}",
        ".text-block { position: absolute; }",
        ".image-block { position: absolute; }",
        ".image-block img { width: 100%; height: 100%; object-fit: contain; }",
        "</style>",
        "</head>",
        "<body>",
    ]

    for i in range(start, end + 1):
        page = doc[i]
        page_width = page.rect.width
        page_height = page.rect.height

        scale_factor = 2.0  # 渲染分辨率
        mat = fitz.Matrix(scale_factor, scale_factor)
        pix = page.get_pixmap(matrix=mat)
        page_img_bytes = pix.tobytes("png")
        page_img_b64 = base64.b64encode(page_img_bytes).decode("utf-8")

        html_parts.append(
            f'<div class="page" style="width:{page_width}px;height:{page_height}px;'
            f'background:url(data:image/png;base64,{page_img_b64}) no-repeat;'
            f'background-size:100% 100%;">'
        )

        # 文字 overlay
        text_dict = page.get_text("dict")
        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                bbox = line.get("bbox", (0, 0, 0, 0))
                line_text = "".join(
                    span.get("text", "") for span in line.get("spans", [])
                )
                if not line_text.strip():
                    continue

                span = line["spans"][0]
                font_size = span.get("size", 12)
                font_name = span.get("font", "sans-serif")

                html_parts.append(
                    f'<div class="text-block" style="'
                    f'left:{bbox[0]}px;top:{bbox[1]}px;'
                    f'font-size:{font_size}px;font-family:{font_name};'
                    f'white-space:nowrap;">'
                    f'{_escape_html(line_text)}</div>'
                )

        html_parts.append("</div>")

    doc.close()

    html_parts.append("</body></html>")
    html_content = "\n".join(html_parts)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    logger.info("HTML conversion done: %s", output_path)
    return output_path


def _escape_html(text: str) -> str:
    """HTML 转义"""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )
