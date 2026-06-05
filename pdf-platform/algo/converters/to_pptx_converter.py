"""
PDF → PPTX 转换器
每页渲染为背景图 + 可编辑文字 overlay
"""

from __future__ import annotations

import io
import logging
import os

import fitz  # PyMuPDF

from algo.models.params import ConvertParams

logger = logging.getLogger(__name__)


def convert(file_path: str, params: ConvertParams, output_dir: str) -> str:
    """PDF → PPTX 转换

    策略:
    1. 将每页渲染为 PNG 背景图
    2. 在 PowerPoint 幻灯片中插入背景图
    3. 在对应位置 overlay 可编辑文本框

    Returns:
        输出 .pptx 文件路径
    """
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.pptx")

    try:
        from pptx import Presentation
        from pptx.util import Inches, Emu
        from pptx.util import Pt as Pt_
        from pptx.dml.color import RGBColor
    except ImportError:
        logger.error("python-pptx not installed. pip install python-pptx")
        raise

    prs = Presentation()

    doc = fitz.open(file_path)
    start = params.start_page
    end = params.end_page if params.end_page is not None else doc.page_count - 1

    for i in range(start, end + 1):
        page = doc[i]

        # 设置幻灯片大小与 PDF 一致
        prs.slide_width = int(page.rect.width * 914400 / 72)  # pt → EMU
        prs.slide_height = int(page.rect.height * 914400 / 72)

        slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank layout

        # 1. 渲染页面为图片作为背景
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        slide.shapes.add_picture(
            io.BytesIO(img_bytes),
            0, 0,
            width=prs.slide_width,
            height=prs.slide_height,
        )

        # 2. 提取文字并 overlay 文本框
        text_blocks = page.get_text("dict")
        for block in text_blocks.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                bbox = line.get("bbox", (0, 0, 0, 0))
                line_text = "".join(
                    span.get("text", "") for span in line.get("spans", [])
                ).strip()
                if not line_text:
                    continue

                span = line["spans"][0]
                font_size = span.get("size", 12)
                font_color = span.get("color", 0)
                color_rgb = _int_to_rgb(font_color)

                left = bbox[0] * 914400 / 72
                top = bbox[1] * 914400 / 72
                width = (bbox[2] - bbox[0]) * 914400 / 72
                height = (bbox[3] - bbox[1]) * 914400 / 72 + 2000  # 略微增加高度

                txBox = slide.shapes.add_textbox(
                    int(left), int(top), int(width), int(height)
                )
                tf = txBox.text_frame
                tf.word_wrap = True
                p = tf.paragraphs[0]
                p.text = line_text

                p.font.size = Pt_(font_size)
                if font_color:
                    p.font.color.rgb = RGBColor(*color_rgb)

    doc.close()
    prs.save(output_path)
    logger.info("PPTX conversion done: %s", output_path)
    return output_path


def _int_to_rgb(color_int: int) -> tuple[int, int, int]:
    """将 PyMuPDF 颜色整数转为 RGB tuple"""
    r = (color_int >> 16) & 0xFF
    g = (color_int >> 8) & 0xFF
    b = color_int & 0xFF
    return (r, g, b)
