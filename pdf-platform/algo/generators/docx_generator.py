"""
DOCXGenerator — DocumentModel → 可编辑 .docx。

从 :class:`~algo.document_model.DocumentModel` 生成语义结构化的 Word 文档：

- title 块 → Word Heading（按 heading_level）
- text 块 → Paragraph（保留 run 级字体/粗体/颜色）
- table 块 → Word Table（保留合并单元格、表头样式）
- image 块 → Inline image（按比例缩放）
- 多列布局 → Word section columns（通过 OOXML）
- 阅读顺序 → 文档内容顺序
- 公式 → 纯文本 LaTeX（Word 原生 OMML 转换留作扩展）

设计要点
--------
- 语义优先：生成可编辑、可重排的文档，而非像素精确的布局复制。
  这与 DOCX 的格式本质（流式布局）一致。
- 字体元数据保留：每个 run 的字体名、字号、粗体、颜色都写入。
- 中文字体回退：未指定字体或字体含 CJK 标记时用 fallback_font。
"""

from __future__ import annotations

import io
import logging
import os
from typing import Optional

from algo.document_model import DocumentModel, LayoutBlock, Page, TableBlock, TextRun
from algo.models.params import ConvertParams

logger = logging.getLogger(__name__)


def generate_docx(
    model: DocumentModel,
    output_path: str,
    params: Optional[ConvertParams] = None,
) -> str:
    """从 DocumentModel 生成 DOCX 文件。

    Args:
        model: 解析阶段产出的文档模型。
        output_path: 输出 .docx 文件路径。
        params: 转换参数（使用 font.fallback_font 等）。

    Returns:
        输出文件路径。
    """
    if params is None:
        params = ConvertParams()

    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()

    # 设置默认字体
    _set_default_font(doc, params.font.fallback_font)

    for page_idx, page in enumerate(model.pages):
        if page_idx > 0:
            doc.add_page_break()

        # 多列处理：如果当前页检测到多列，创建分节
        if page.has_multiple_columns and len(page.text_blocks) >= 4:
            _add_section_with_columns(doc, num_cols=2)
        elif page_idx > 0:
            # 恢复单列
            _add_section_with_columns(doc, num_cols=1)

        # 按阅读顺序输出块
        for block in page.sorted_blocks:
            _write_block_to_docx(doc, block, page, params)

    doc.save(output_path)
    logger.info("DOCX generated: %s", output_path)
    return output_path


def _set_default_font(doc, font_name: str):
    """设置文档默认字体。"""
    style = doc.styles["Normal"]
    style.font.name = font_name
    # 设置东亚字体
    from docx.oxml.ns import qn
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        from docx.oxml import OxmlElement
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), font_name)


def _add_section_with_columns(doc, num_cols: int):
    """通过 OOXML 设置分节列数。"""
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    section = doc.sections[-1]
    sect_pr = section._sectPr
    # 移除已有 cols
    for existing in sect_pr.findall(qn("w:cols")):
        sect_pr.remove(existing)

    cols = OxmlElement("w:cols")
    cols.set(qn("w:num"), str(num_cols))
    cols.set(qn("w:space"), "720")  # 列间距，单位 twips (0.5 inch)
    sect_pr.append(cols)


def _write_block_to_docx(
    doc,
    block: LayoutBlock,
    page: Page,
    params: ConvertParams,
):
    """将单个版面块写入 DOCX。"""
    if block.block_type == "title":
        _write_heading(doc, block, params)
    elif block.block_type == "text":
        _write_paragraph(doc, block, params)
    elif block.block_type == "list":
        _write_list_item(doc, block, params)
    elif block.block_type == "table" and block.table:
        _write_table(doc, block.table, params)
    elif block.block_type == "image" and block.image:
        _write_image(doc, block, page, params)
    elif block.block_type == "formula" and block.formula:
        _write_formula(doc, block, params)
    elif block.block_type in ("header", "footer"):
        # 页眉页脚内容作为普通段落保留（可选跳过）
        _write_paragraph(doc, block, params)
    elif block.block_type == "caption":
        _write_caption(doc, block, params)


def _write_heading(doc, block: LayoutBlock, params: ConvertParams):
    """写入标题。"""
    level = block.heading_level or 1
    level = min(max(level, 1), 9)
    text = block.text.strip()
    if not text:
        return

    heading = doc.add_heading(text, level=level)
    _apply_runs_to_paragraph(heading, block.runs, params)


def _write_paragraph(doc, block: LayoutBlock, params: ConvertParams):
    """写入段落。"""
    text = block.text.strip()
    if not text:
        return

    para = doc.add_paragraph()
    _apply_runs_to_paragraph(para, block.runs, params)


def _write_list_item(doc, block: LayoutBlock, params: ConvertParams):
    """写入列表项。"""
    text = block.text.strip()
    if not text:
        return

    para = doc.add_paragraph(style="List Bullet")
    _apply_runs_to_paragraph(para, block.runs, params)


def _write_caption(doc, block: LayoutBlock, params: ConvertParams):
    """写入图/表标题（斜体居中）。"""
    text = block.text.strip()
    if not text:
        return

    from docx.enum.text import WD_ALIGN_PARAGRAPH
    para = doc.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _apply_runs_to_paragraph(para, block.runs, params)
    for run in para.runs:
        run.italic = True


def _write_table(doc, table: TableBlock, params: ConvertParams):
    """写入表格，保留合并单元格。"""
    if table.rows == 0 or table.cols == 0:
        return

    from docx.shared import Pt

    doc_table = doc.add_table(rows=table.rows, cols=table.cols)
    doc_table.style = "Table Grid"

    # 标记哪些单元格已被合并占据，避免重复写入
    occupied = [[False] * table.cols for _ in range(table.rows)]

    for cell in table.cells:
        r, c = cell.row, cell.col
        if r >= table.rows or c >= table.cols:
            continue
        if occupied[r][c]:
            continue

        doc_cell = doc_table.cell(r, c)

        # 处理合并
        if cell.rowspan > 1 or cell.colspan > 1:
            end_r = min(r + cell.rowspan - 1, table.rows - 1)
            end_c = min(c + cell.colspan - 1, table.cols - 1)
            merged = doc_cell.merge(doc_table.cell(end_r, end_c))
            doc_cell = merged
            # 标记被合并覆盖的格子
            for rr in range(r, end_r + 1):
                for cc in range(c, end_c + 1):
                    if rr != r or cc != c:
                        occupied[rr][cc] = True

        # 写入文本
        cell_text = "".join(run.text for run in cell.runs).strip()
        if cell_text:
            para = doc_cell.paragraphs[0]
            _apply_runs_to_paragraph(para, cell.runs, params)

        # 表头加粗
        if cell.is_header:
            for para in doc_cell.paragraphs:
                for run in para.runs:
                    run.bold = True


def _write_image(doc, block: LayoutBlock, page: Page, params: ConvertParams):
    """写入图片。"""
    img = block.image
    if img is None:
        return

    # 获取图片字节
    if img.image_bytes:
        img_stream = io.BytesIO(img.image_bytes)
    elif img.image_path and os.path.isfile(img.image_path):
        with open(img.image_path, "rb") as f:
            img_stream = io.BytesIO(f.read())
    else:
        return

    # 按页面比例计算宽度
    from docx.shared import Inches
    bbox_width = block.bbox.width  # 归一化宽度 [0,1]
    # 页面可用宽度约 6.5 inch（letter 减去边距）
    max_width = 6.5
    width_in = max_width * bbox_width
    width_in = max(1.0, min(width_in, max_width))  # 限制范围

    try:
        doc.add_picture(img_stream, width=Inches(width_in))
        # 图片后加换行
        doc.add_paragraph()
    except Exception as e:
        logger.warning("Failed to insert image: %s", e)


def _write_formula(doc, block: LayoutBlock, params: ConvertParams):
    """写入公式（当前以 LaTeX 纯文本形式保留）。"""
    formula = block.formula
    if formula is None or not formula.latex:
        return

    para = doc.add_paragraph()
    run = para.add_run(formula.latex)
    run.italic = True


def _apply_runs_to_paragraph(para, runs: list[TextRun], params: ConvertParams):
    """将 TextRun 列表应用到 docx 段落，保留字体元数据。"""
    from docx.shared import Pt, RGBColor

    if not runs:
        return

    for run_data in runs:
        if not run_data.text:
            continue
        run = para.add_run(run_data.text)

        # 字体名
        if run_data.font_name:
            run.font.name = run_data.font_name
        else:
            run.font.name = params.font.fallback_font

        # 设置东亚字体
        from docx.oxml.ns import qn
        rpr = run._element.get_or_add_rPr()
        rfonts = rpr.find(qn("w:rFonts"))
        if rfonts is None:
            from docx.oxml import OxmlElement
            rfonts = OxmlElement("w:rFonts")
            rpr.append(rfonts)
        rfonts.set(qn("w:eastAsia"), params.font.fallback_font)

        # 字号
        if run_data.font_size and params.font.preserve_size:
            run.font.size = Pt(run_data.font_size)

        # 粗体 / 斜体 / 下划线
        if run_data.bold:
            run.bold = True
        if run_data.italic:
            run.italic = True
        if run_data.underline:
            run.underline = True

        # 颜色
        if run_data.color:
            rgb = _hex_to_rgb(run_data.color)
            if rgb:
                run.font.color.rgb = RGBColor(*rgb)


def _hex_to_rgb(hex_str: str) -> Optional[tuple[int, int, int]]:
    """'#RRGGBB' → (r, g, b)。"""
    try:
        hex_str = hex_str.lstrip("#")
        if len(hex_str) == 6:
            return (int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))
    except (ValueError, IndexError):
        pass
    return None
