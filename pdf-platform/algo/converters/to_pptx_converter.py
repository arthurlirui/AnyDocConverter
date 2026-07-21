"""
PDF → PPTX 转换器。

策略：每页渲染为 PNG 背景图 + 在原坐标处叠加可编辑文本框，
使幻灯片既保留视觉版式，又允许用户选中文本进行编辑。
"""

from __future__ import annotations

import io
import logging
import os

import fitz  # PyMuPDF

from algo.models.params import ConvertParams

logger = logging.getLogger(__name__)

# 1 pt = 914400 EMU（Office Open XML 内部长度单位）
_EMU_PER_PT = 914400 / 72


def convert(file_path: str, params: ConvertParams, output_dir: str) -> str:
    """PDF → PPTX 转换。

    每页生成一张幻灯片：底层为 150 DPI 渲染的页面背景图，上层为按
    PDF 文本块坐标放置的可编辑文本框（保留字号与颜色）。

    Args:
        file_path: 源 PDF 文件路径。
        params: 转换参数（使用 start_page / end_page）。
        output_dir: 输出目录（不存在会自动创建）。

    Returns:
        输出 .pptx 文件路径。
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
    # 限定 end 在合法页码范围内，避免 IndexError
    end = params.end_page if params.end_page is not None else doc.page_count - 1
    end = min(end, doc.page_count - 1)
    if start > end:
        doc.close()
        raise ValueError(
            f"Invalid page range: start_page={start} > end_page={end}"
        )

    for i in range(start, end + 1):
        page = doc[i]

        # 仅在第一页时固定幻灯片尺寸。python-pptx 的 slide_width/height 是
        # 全局属性，循环内重复设置会反向影响已创建的幻灯片导致版面错乱。
        # 混合页面尺寸的 PDF 会以首页为准，统一渲染。
        if i == start:
            prs.slide_width = int(page.rect.width * _EMU_PER_PT)  # pt → EMU
            prs.slide_height = int(page.rect.height * _EMU_PER_PT)

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

                left = bbox[0] * _EMU_PER_PT
                top = bbox[1] * _EMU_PER_PT
                width = (bbox[2] - bbox[0]) * _EMU_PER_PT
                height = (bbox[3] - bbox[1]) * _EMU_PER_PT + 2000  # 略微增加高度

                txBox = slide.shapes.add_textbox(
                    int(left), int(top), int(width), int(height)
                )
                tf = txBox.text_frame
                tf.word_wrap = True
                p = tf.paragraphs[0]
                p.text = line_text

                p.font.size = Pt_(font_size)
                # font_color == 0 表示纯黑。原代码用 `if font_color:` 会漏掉
                # 黑色文本（0 为 falsy），导致颜色未被正确写入。这里改为显式
                # 判断是否为非负整数，确保所有有效颜色都被设置。
                if font_color is not None and font_color >= 0:
                    p.font.color.rgb = RGBColor(*color_rgb)

    doc.close()
    prs.save(output_path)
    logger.info("PPTX conversion done: %s", output_path)
    return output_path


def _int_to_rgb(color_int: int) -> tuple[int, int, int]:
    """将 PyMuPDF 颜色整数（0xRRGGBB）转为 ``(r, g, b)`` 元组。"""
    r = (color_int >> 16) & 0xFF
    g = (color_int >> 8) & 0xFF
    b = color_int & 0xFF
    return (r, g, b)

