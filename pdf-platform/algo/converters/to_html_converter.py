"""
PDF → HTML 转换器
文字 + 图片 → HTML + CSS
"""

from __future__ import annotations

import base64
import logging
import os

import fitz  # PyMuPDF

from algo.models.params import ConvertParams
from algo.ocr.ocr_text import is_image_file, ocr_image_to_text, ocr_pdf_to_text

logger = logging.getLogger(__name__)


def convert(file_path: str, params: ConvertParams, output_dir: str) -> str:
    """PDF → HTML 转换

    策略:
    1. 普通文本 PDF：每页渲染为 div，绝对定位文字 overlay，背景图内嵌 base64。
    2. 扫描版 PDF / 图片输入：走 OCR 提取纯文本，输出最小 HTML 文档，
       避免 fitz.open 解析图片失败或扫描页无文字块导致空页面。

    Args:
        file_path: 源 PDF 或图片文件路径
        params: 转换参数
        output_dir: 输出目录（不存在会自动创建）

    Returns:
        输出 .html 文件路径
    """
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.html")

    if is_image_file(file_path):
        text = ocr_image_to_text(file_path, params).strip()
        _write_text_html(output_path, base_name, text)
        logger.info("HTML conversion done (image+OCR): %s", output_path)
        return output_path
    if params.ocr.enabled:
        text = ocr_pdf_to_text(file_path, params).strip()
        _write_text_html(output_path, base_name, text)
        logger.info("HTML conversion done (PDF+OCR): %s", output_path)
        return output_path

    doc = fitz.open(file_path)
    start = params.start_page
    end = params.end_page if params.end_page is not None else doc.page_count - 1
    # 限定 end 在合法范围内，避免越界 IndexError
    end = min(end, doc.page_count - 1)
    if start > end:
        doc.close()
        raise ValueError(
            f"Invalid page range: start_page={start} > end_page={end}"
        )

    html_parts = [
        "<!DOCTYPE html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f"<title>{_escape_html(base_name)}</title>",
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
                # 字体名来自 PDF 内嵌资源，可能含特殊字符；转义后再放进 CSS
                font_name = _escape_html(span.get("font", "sans-serif"))

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
    """HTML 转义 — 转义 5 个核心字符，防止注入与渲染错乱。"""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )


def _write_text_html(output_path: str, base_name: str, text: str) -> None:
    """将 OCR 提取的纯文本写入一个最小 HTML 文档。

    扫描版 / 图片输入无法走版式重建路径，这里输出语义化 HTML，
    每一行作为一段，保留可读性。空文本时给出明确提示。
    """
    body_lines = text.split("\n") if text else ["(No OCR text recognized)"]
    paragraphs = "\n".join(
        f"  <p>{_escape_html(line)}</p>" for line in body_lines if line.strip()
    ) or "  <p>(No OCR text recognized)</p>"

    html = (
        "<!DOCTYPE html>\n"
        '<html lang="zh-CN">\n'
        "<head>\n"
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        f"<title>{_escape_html(base_name)}</title>\n"
        "<style>\n"
        "body { font-family: 'Noto Sans CJK SC', sans-serif; "
        "max-width: 800px; margin: 2em auto; line-height: 1.6; color: #222; }\n"
        "p { margin: 0 0 0.6em 0; }\n"
        "</style>\n"
        "</head>\n"
        "<body>\n"
        f"{paragraphs}\n"
        "</body>\n"
        "</html>\n"
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
